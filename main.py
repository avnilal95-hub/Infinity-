import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
import time
import sqlite3
from collections import defaultdict
from dotenv import load_dotenv

# ==============================================================================
# 🌐 ENVIRONMENT & CONFIGURATION SETUP
# ==============================================================================

# Load local environment variables (Railway uses its own Variables dashboard)
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Core Channel & Role Identifiers Configuration
WELCOME_CHANNEL_ID = 1533142133874364426
VISIT_CHANNEL_ID = 1533140423370084435

BOOST_ANNOUNCE_CHANNEL_ID = 1533142072666882098
BOOST_LOG_CHANNEL_ID = 1533142643914178570
BOOST_ROLE_ID = 1533160053224509480

# Rank Progression Milestone Notification Channels & Target Channel
RANK_NOTIFY_CHANNEL_1 = 1533142643914178570
RANK_NOTIFY_CHANNEL_2 = 1533143101063958608
LEADERBOARD_CHANNEL_ID = 1533143222530871337

# Audit and Moderation Event Log Channel (reusing standard log or dedicated channel)
AUDIT_LOG_CHANNEL_ID = 1533142643914178570

# Complete Role Milestones Mapping (Required Message Counts -> Discord Role IDs)
ROLE_MILESTONES = [
    (1, 1533145946706284644),
    (500, 1533146015807574297),
    (1000, 1533146130660196362),
    (2500, 1533146195491557427),
    (5000, 1533146318279540881),
    (10000, 1533146426744508506),
    (15000, 1533146562505605120),
    (25000, 1533146705845944450),
    (35000, 1533146788255498352),
    (50000, 1533146891666198830)
]

# ==============================================================================
# 🗄️ ADVANCED SQLITE DATABASE ARCHITECTURE
# ==============================================================================

def init_db():
    """Initializes the SQLite database and constructs required tables for persistence."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # Table 1: User Message Counts & Progression Tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_messages (
            user_id INTEGER PRIMARY KEY,
            message_count INTEGER DEFAULT 0,
            last_message_timestamp REAL DEFAULT 0
        )
    ''')
    
    # Table 2: Moderation Warnings System
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_warnings (
            warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            moderator_id INTEGER,
            reason TEXT,
            timestamp REAL
        )
    ''')
    
    # Table 3: User Profiles & Custom Status / Nicknames
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            reputation INTEGER DEFAULT 0,
            bio TEXT DEFAULT 'No biography set.'
        )
    ''')
    
    conn.commit()
    conn.close()

def add_message(user_id: int):
    """Increments and returns the updated message count for a specific user ID."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT message_count FROM user_messages WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    current_time = time.time()
    if row:
        new_count = row[0] + 1
        cursor.execute('''
            UPDATE user_messages 
            SET message_count = ?, last_message_timestamp = ? 
            WHERE user_id = ?
        ''', (new_count, current_time, user_id))
    else:
        new_count = 1
        cursor.execute('''
            INSERT INTO user_messages (user_id, message_count, last_message_timestamp) 
            VALUES (?, ?, ?)
        ''', (user_id, new_count, current_time))
        
    conn.commit()
    conn.close()
    return new_count

def get_user_messages(user_id: int):
    """Retrieves the total accumulated message count for an individual user."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT message_count FROM user_messages WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def get_top_users(limit=100):
    """Fetches the top members ordered by message count descending."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, message_count 
        FROM user_messages 
        ORDER BY message_count DESC 
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_warning(user_id: int, mod_id: int, reason: str):
    """Records a new moderation warning and returns the updated total warnings count."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_warnings (user_id, moderator_id, reason, timestamp) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, mod_id, reason, time.time()))
    conn.commit()
    
    cursor.execute('SELECT COUNT(*) FROM user_warnings WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_warnings(user_id: int):
    """Retrieves all warning entries issued against a specific user."""
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT moderator_id, reason, timestamp 
        FROM user_warnings 
        WHERE user_id = ?
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ==============================================================================
# 🤖 BOT SETUP & INTENTS CONFIGURATION
# ==============================================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.guilds = True
intents.bans = True
intents.emojis = True

class InfinityBot(commands.Bot):
    """Custom subclassed Bot instance managing advanced caching, background tasks, and hooks."""
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.anti_spam_cache = defaultdict(list)
        self.command_cooldowns = defaultdict(float)

    async def setup_hook(self):
        """Executes asynchronous startup procedures including DB creation and global tree sync."""
        init_db()
        weekly_leaderboard.start()
        await self.tree.sync()
        print("⚡ Advanced enterprise database, UI components, & slash commands synced globally!")

bot = InfinityBot()

@bot.event
async def on_ready():
    """Event listener triggered upon successful bot authentication and connection."""
    print(f"🤖 Securely logged in as {bot.user} (ID: {bot.user.id})")
    print(f"🔗 Connected to {len(bot.guilds)} active server(s).")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="over Infinity Community"))

# ==============================================================================
# 🛡️ AUTOMOD, ANTI-SPAM & REAL-TIME EVENT LISTENERS
# ==============================================================================

@bot.event
async def on_message(message: discord.Message):
    """Core real-time message handler processing chat activity, anti-spam, and leveling."""
    if message.author.bot or not message.guild:
        return

    # Process standard commands if any prefix commands are used
    await bot.process_commands(message)

    # 1. Message Progression System Tracking
    total_msgs = add_message(message.author.id)
    
    # Check Role Milestone Triggers
    for i, (req_msgs, role_id) in enumerate(ROLE_MILESTONES):
        if total_msgs == req_msgs:
            guild = message.guild
            member = message.author
            role = guild.get_role(role_id)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role)
                    prev_role_id = ROLE_MILESTONES[i-1][1] if i > 0 else None
                    
                    # Notify in designated progression notification channels
                    for ch_id in [RANK_NOTIFY_CHANNEL_1, RANK_NOTIFY_CHANNEL_2]:
                        ch = bot.get_channel(ch_id)
                        if ch:
                            notif_embed = discord.Embed(
                                title="🎉 Advanced Rank Milestone Reached!",
                                description=(
                                    f"{member.mention} you have ranked up from\n"
                                    f"➡️ " + (f"<@&{prev_role_id}>" if prev_role_id else "Starting Level") + "\n"
                                    f"➡️ <@&{role_id}>"
                                ),
                                color=0x00FF66,
                                timestamp=discord.utils.utcnow()
                            )
                            if member.display_avatar:
                                notif_embed.set_thumbnail(url=member.display_avatar.url)
                            notif_embed.set_footer(text=f"Total Messages: {total_msgs}")
                            await ch.send(content=member.mention, embed=notif_embed)
                except discord.Forbidden:
                    pass

    # 2. Advanced Anti-Spam Security Filter
    author_id = message.author.id
    current_time = time.time()
    
    bot.anti_spam_cache[author_id].append(current_time)
    bot.anti_spam_cache[author_id] = [
        t for t in bot.anti_spam_cache[author_id] 
        if current_time - t < 4.0
    ]
    
    if len(bot.anti_spam_cache[author_id]) > 5:
        bot.anti_spam_cache[author_id] = []
        try:
            await message.delete()
            warn_embed = discord.Embed(
                title="⚠️ Automated Security Warning",
                description=f"{message.author.mention}, please slow down! You are triggering anti-spam protection filters.",
                color=0xFF4747
            )
            warning_msg = await message.channel.send(embed=warn_embed)
            await asyncio.sleep(5)
            await warning_msg.delete()
        except discord.Forbidden:
            pass

@bot.event
async def on_message_delete(message: discord.Message):
    """Audits deleted messages and logs them to the designated audit channel."""
    if message.author.bot or not message.guild:
        return
    log_channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)
    if log_channel and message.content:
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            description=f"**Author:** {message.author.mention} (`{message.author.id}`)\n**Channel:** {message.channel.mention}",
            color=0xFF4747,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Content", value=message.content[:1024], inline=False)
        await log_channel.send(embed=embed)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """Audits edited messages and logs content modifications."""
    if before.author.bot or not before.guild or before.content == after.content:
        return
    log_channel = bot.get_channel(AUDIT_LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title="✏️ Message Edited",
            description=f"**Author:** {before.author.mention} (`{before.author.id}`)\n**Channel:** {before.channel.mention}",
            color=0xFFA500,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Before", value=before.content[:1024] or "[Empty]", inline=False)
        embed.add_field(name="After", value=after.content[:1024] or "[Empty]", inline=False)
        await log_channel.send(embed=embed)

# ==============================================================================
# 👋 WELCOME & 🚀 BOOST EVENT HANDLERS
# ==============================================================================

@bot.event
async def on_member_join(member: discord.Member):
    """Welcomes new members joining the guild with rich embeds and channel references."""
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel: 
        embed = discord.Embed(
            title="👋 Welcome to the Server!",
            description=(
                f"{member.mention} thanks for joining **{member.guild.name}**\n\n"
                f"Please visit \n➔ <#{VISIT_CHANNEL_ID}>"
            ),
            color=0x00E5FF,
            timestamp=discord.utils.utcnow()
        )
        if member.guild.icon:
            embed.set_thumbnail(url=member.guild.icon.url)
        embed.set_footer(text=f"Member #{member.guild.member_count}")
        await channel.send(content=member.mention, embed=embed)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """Tracks server boost updates and rewards boosters automatically."""
    if before.premium_since is None and after.premium_since is not None:
        announce_channel = bot.get_channel(BOOST_ANNOUNCE_CHANNEL_ID)
        if announce_channel:
            embed1 = discord.Embed(
                title="🚀 New Server Booster!",
                description=(
                    f"{after.mention} thanks for boosting! You have earned role:\n"
                    f"=><@&{BOOST_ROLE_ID}>"
                ),
                color=0xF47FFF
            )
            if after.avatar:
                embed1.set_thumbnail(url=after.avatar.url)
            await announce_channel.send(content=after.mention, embed=embed1)

        log_channel = bot.get_channel(BOOST_LOG_CHANNEL_ID)
        if log_channel:
            embed2 = discord.Embed(
                description=f"💎 {after.mention} received <@&{BOOST_ROLE_ID}> for boosting the server.",
                color=0xF47FFF
            )
            await log_channel.send(content=after.mention, embed=embed2)

# ==============================================================================
# 📊 PAGINATED LEADERBOARD VIEW & RANK COMMANDS
# ==============================================================================

def make_progress_bar(current, maximum):
    """Constructs a visual progress bar string using square emojis."""
    if maximum == 0:
        return "🟩" * 10
    percent = min(current / maximum, 1.0)
    filled = int(round(percent * 10))
    return "🟩" * filled + "⬛" * (10 - filled)

class LeaderboardPagination(discord.ui.View):
    """Interactive Discord UI View providing pagination buttons for the rank leaderboard."""
    def __init__(self, data):
        super().__init__(timeout=120)
        self.data = data
        self.current_page = 0
        self.per_page = 10
        self.max_pages = max(1, (len(data) - 1) // self.per_page + 1)
        self.update_buttons()

    def update_buttons(self):
        """Enables or disables pagination buttons depending on the current page index."""
        self.prev_btn.disabled = self.current_page == 0
        self.next_btn.disabled = self.current_page >= self.max_pages - 1

    def create_embed(self, guild):
        """Generates the leaderboard embed for the active page slice."""
        embed = discord.Embed(
            title=f"🏆 Advanced Server Leaderboard (Page {self.current_page + 1}/{self.max_pages})",
            color=0xFFD700,
            timestamp=discord.utils.utcnow()
        )
        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        chunk = self.data[start_idx:end_idx]
        
        desc = ""
        for idx, (uid, msgs) in enumerate(chunk, start_idx + 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`#{idx}`"
            desc += f"{medal} <@{uid}> — **{msgs}** messages\n"
            
        embed.description = desc if desc else "No users found on this page."
        return embed

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handles page navigation backward."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(interaction.guild), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handles page navigation forward."""
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(interaction.guild), view=self)

@bot.tree.command(name="rank", description="Check your detailed message progression profile and visual rank bar.")
@app_commands.describe(member="The member you want to look up (optional)")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    """Slash command to view a user's current rank, message count, and progress bar."""
    target = member or interaction.user
    count = get_user_messages(target.id)
    
    current_role = "None"
    next_role = "Max Rank Reached!"
    next_target_msgs = 50000
    
    active_idx = -1
    for i, (req, r_id) in enumerate(ROLE_MILESTONES):
        if count >= req:
            active_idx = i
            
    if active_idx != -1:
        current_role = f"<@&{ROLE_MILESTONES[active_idx][1]}>"
        if active_idx + 1 < len(ROLE_MILESTONES):
            next_role = f"<@&{ROLE_MILESTONES[active_idx + 1][1]}>"
            next_target_msgs = ROLE_MILESTONES[active_idx + 1][0]
        else:
            next_target_msgs = ROLE_MILESTONES[active_idx][0]
    else:
        next_role = f"<@&{ROLE_MILESTONES[0][1]}>"
        next_target_msgs = ROLE_MILESTONES[0][0]

    progress_bar = make_progress_bar(count, next_target_msgs)

    embed = discord.Embed(
        title=f"📊 Member Profile — {target.display_name}",
        color=0x00E5FF,
        timestamp=discord.utils.utcnow()
    )
    if target.display_avatar:
        embed.set_thumbnail(url=target.display_avatar.url)
    if interaction.guild.icon:
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url)

    embed.add_field(name="Current Rank Name", value=current_role, inline=False)
    embed.add_field(name="User Progression", value=f"{progress_bar}\n**{count}** / **{next_target_msgs}** messages", inline=False)
    embed.add_field(name="Total Messages Sent", value=f"💬 {count}", inline=True)
    embed.add_field(name="Next Target Role", value=next_role, inline=True)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ranklist", description="View the interactive paginated top message leaderboard.")
async def ranklist(interaction: discord.Interaction):
    """Slash command displaying the interactive paginated message leaderboard."""
    top_users = get_top_users(100)
    if not top_users:
        return await interaction.response.send_message("❌ No message statistics recorded yet!", ephemeral=True)
        
    view = LeaderboardPagination(top_users)
    embed = view.create_embed(interaction.guild)
    await interaction.response.send_message(embed=embed, view=view)

# ==============================================================================
# 🛠️ ADVANCED MODERATION & UTILITY COMMANDS
# ==============================================================================

@bot.tree.command(name="clear", description="Bulk delete a specified number of messages.")
@app_commands.describe(amount="Number of messages to delete (max 500)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    """Bulk purges messages from the current text channel safely."""
    if amount > 500:
        return await interaction.response.send_message("❌ Cannot clear more than **500** messages at once.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    
    success_embed = discord.Embed(
        description=f"✅ Successfully purged **{len(deleted)}** messages from this channel.",
        color=0x00FF66
    )
    await interaction.followup.send(embed=success_embed, ephemeral=True)

@bot.tree.command(name="warn", description="Issue an official moderation warning to a user.")
@app_commands.describe(member="The member to warn", reason="The reason for the warning")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    """Issues a formal warning saved inside the database audit logs."""
    total_warnings = add_warning(member.id, interaction.user.id, reason)
    embed = discord.Embed(
        title="⚠️ Member Warned",
        description=f"{member.mention} has been warned by {interaction.user.mention}.\n**Reason:** {reason}\n**Total Warnings:** {total_warnings}",
        color=0xFF4747,
        timestamp=discord.utils.utcnow()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="warnings", description="Check active warnings for a member.")
@app_commands.describe(member="The member to check")
@app_commands.checks.has_permissions(moderate_members=True)
async def warnings(interaction: discord.Interaction, member: discord.Member):
    """Retrieves all warning logs associated with a particular member."""
    user_warns = get_warnings(member.id)
    embed = discord.Embed(
        title=f"📋 Warning Logs for {member.display_name}",
        color=0xFFA500,
        timestamp=discord.utils.utcnow()
    )
    if not user_warns:
        embed.description = "✅ This user has a clean record with zero warnings!"
    else:
        desc = ""
        for idx, (mod_id, reason, ts) in enumerate(user_warns, 1):
            desc += f"`#{idx}` Moderator: <@{mod_id}> | Reason: *{reason}*\n"
        embed.description = desc
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Check the bot's current websocket latency response time.")
async def ping(interaction: discord.Interaction):
    """Ping command returning real-time latency stats."""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot Websocket Latency: **{latency}ms**",
        color=0x00FF66,
        timestamp=discord.utils.utcnow()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==============================================================================
# 🔄 AUTOMATED BACKGROUND TASKS (WEEKLY LEADERBOARD)
# ==============================================================================

@tasks.loop(hours=168)
async def weekly_leaderboard():
    """Background task executing every 7 days to post top 100 rankings automatically."""
    top_100 = get_top_users(100)
    if not top_100:
        return
        
    ch = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not ch:
        return
        
    embed = discord.Embed(
        title="👑 Automated Weekly Top 100 Leaderboard",
        description="Here are our community's most active members over the past week!",
        color=0xFFD700,
        timestamp=discord.utils.utcnow()
    )
    
    chunk1 = ""
    for idx, (uid, msgs) in enumerate(top_100[:25], 1):
        chunk1 += f"`#{idx}` <@{uid}> — **{msgs}** msgs\n"
    embed.add_field(name="Top 1 - 25", value=chunk1 if chunk1 else "None", inline=False)
    
    if len(top_100) > 25:
        chunk2 = ""
        for idx, (uid, msgs) in enumerate(top_100[25:50], 26):
            chunk2 += f"`#{idx}` <@{uid}> — **{msgs}** msgs\n"
        embed.add_field(name="Top 26 - 50", value=chunk2, inline=False)

    await ch.send(embed=embed)

@weekly_leaderboard.before_loop
async def before_weekly_leaderboard():
    """Ensures the background task waits for the bot to become fully operational before looping."""
    await bot.wait_until_ready()

# ==============================================================================
# 🚫 GLOBAL ERROR HANDLERS
# ==============================================================================

@clear.error
@warn.error
@warnings.error
async def mod_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Catches and handles missing permission errors for slash commands gracefully."""
    if isinstance(error, app_commands.MissingPermissions):
        missing = ", ".join(error.missing_permissions)
        error_embed = discord.Embed(
            description=f"🚫 {interaction.user.mention}, you lack the required permission: `{missing}`",
            color=0xFF4747
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    else:
        raise error

# ==============================================================================
# 🚀 APPLICATION ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: BOT_TOKEN environment variable is missing from configuration!")
    else:
        print("🚀 Initializing bot runtime services...")
        bot.run(TOKEN)
