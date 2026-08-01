import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import time
from collections import defaultdict
from dotenv import load_dotenv

# Load local environment variables (Railway uses its own Variables dashboard)
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# ==========================================
# ⚙️ CONFIGURATION (IDs & SETTINGS)
# ==========================================
WELCOME_CHANNEL_ID = 1533142133874364426
VISIT_CHANNEL_ID = 1533140423370084435

BOOST_ANNOUNCE_CHANNEL_ID = 1533142072666882098
BOOST_LOG_CHANNEL_ID = 1533142643914178570
BOOST_ROLE_ID = 1533160053224509480

# Setup Intents (All intents turned on)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

class InfinityBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.anti_spam_cache = defaultdict(list)

    async def setup_hook(self):
        # Sync slash commands globally
        await self.tree.sync()
        print("⚡ Slash commands synced globally!")

bot = InfinityBot()

@bot.event
async def on_ready():
    print(f"🤖 Bot is ONLINE as {bot.user} (ID: {bot.user.id})")


# ==========================================
# 🛡️ AUTOMOD & ANTI-SPAM SYSTEM
# ==========================================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    # Anti-Spam Logic
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
                title="⚠️ Auto-Mod Warning",
                description=f"{message.author.mention}, please slow down! You are sending messages too quickly.",
                color=0xFF4747
            )
            warning_msg = await message.channel.send(embed=warn_embed)
            await asyncio.sleep(5)
            await warning_msg.delete()
        except discord.Forbidden:
            pass


# ==========================================
# 👋 WELCOME SYSTEM
# ==========================================
@bot.event
async def on_member_join(member: discord.Member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel: 
        embed = discord.Embed(
            title="👋 Welcome to the Server!",
            description=(
                f"{member.mention} thanks for joining **{member.guild.name}**\n\n"
                f"Visit \n➔ <#{VISIT_CHANNEL_ID}>"
            ),
            color=0x00E5FF,
            timestamp=discord.utils.utcnow()
        )
        if member.guild.icon:
            embed.set_thumbnail(url=member.guild.icon.url)
        embed.set_footer(text=f"Member #{member.guild.member_count}")
        await channel.send(content=member.mention, embed=embed)


# ==========================================
# 🚀 SERVER BOOST TRACKER
# ==========================================
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.premium_since is None and after.premium_since is not None:
        
        # 1. Announcement Channel Message
        announce_channel = bot.get_channel(BOOST_ANNOUNCE_CHANNEL_ID)
        if announce_channel:
            embed1 = discord.Embed(
                title="🚀 New Server Booster!",
                description=(
                    f"{after.mention} thanks for boosting you will get\n"
                    f"=><@&{BOOST_ROLE_ID}>"
                ),
                color=0xF47FFF
            )
            if after.avatar:
                embed1.set_thumbnail(url=after.avatar.url)
            await announce_channel.send(content=after.mention, embed=embed1)

        # 2. Log Channel Message
        log_channel = bot.get_channel(BOOST_LOG_CHANNEL_ID)
        if log_channel:
            embed2 = discord.Embed(
                description=f"{after.mention} got this <@&{BOOST_ROLE_ID}> for boosting the server",
                color=0xF47FFF
            )
            await log_channel.send(content=after.mention, embed=embed2)


# ==========================================
# 🗑️ /CLEAR COMMAND
# ==========================================
@bot.tree.command(name="clear", description="Bulk delete messages in this channel.")
@app_commands.describe(amount="Number of messages to delete (max 500)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    if amount > 500:
        embed_limit = discord.Embed(
            description=f"❌ {interaction.user.mention} can't clear more than **500** messages.",
            color=0xFF4747
        )
        return await interaction.response.send_message(embed=embed_limit, ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    
    success_embed = discord.Embed(
        description=f"✅ Successfully cleared **{len(deleted)}** messages.",
        color=0x00FF66
    )
    await interaction.followup.send(embed=success_embed, ephemeral=True)


# ==========================================
# 🚫 PERMISSION ERROR HANDLER
# ==========================================
@clear.error
async def clear_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        missing = ", ".join(error.missing_permissions)
        error_embed = discord.Embed(
            description=f"🚫 {interaction.user.mention} you're lacking permission of `{missing}`",
            color=0xFF4747
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=error_embed, ephemeral=True)
    else:
        raise error


# Run the bot
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: BOT_TOKEN environment variable is missing!")
    else:
        bot.run(TOKEN)
        
