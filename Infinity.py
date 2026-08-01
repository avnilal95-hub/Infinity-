import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from collections import defaultdict
import time

class ServerCore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # ==========================================
        # ⚙️ CONFIGURATION ZONE
        # ==========================================
        # Welcome & Visit
        self.welcome_channel_id = 1533142133874364426
        self.visit_channel_id = 1533140423370084435
        self.autorole_id = 123456789012345678 # Replace with your member role ID
        
        # Boost Tracking
        self.boost_announce_channel_id = 1533142072666882098
        self.boost_log_channel_id = 1533142643914178570
        self.boost_role_id = 1533160053224509480

        # Security & Logging
        self.log_channel_id = 999999999999999999 # Replace with a private staff log channel
        self.anti_spam_cache = defaultdict(list)
        self.spam_limit = 5      # Max messages allowed...
        self.spam_time = 4.0     # ...within this many seconds
        
        # Aesthetics
        self.color_main = 0x00E5FF  # Cyan
        self.color_boost = 0xF47FFF # Nitro Pink
        self.color_warn = 0xFF4747  # Red/Security

    # ==========================================
    # 🛡️ 1. AUTOMOD & ANTI-SPAM SYSTEM
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return

        # Anti-Spam Logic
        author_id = message.author.id
        current_time = time.time()
        
        # Add current message time to the user's cache
        self.anti_spam_cache[author_id].append(current_time)
        
        # Keep only messages sent within the time limit
        self.anti_spam_cache[author_id] = [
            msg_time for msg_time in self.anti_spam_cache[author_id] 
            if current_time - msg_time < self.spam_time
        ]
        
        # Trigger Security if limit exceeded
        if len(self.anti_spam_cache[author_id]) > self.spam_limit:
            self.anti_spam_cache[author_id] = [] # Reset to prevent loop
            
            try:
                await message.delete()
                
                warn_embed = discord.Embed(
                    title="⚠️ Auto-Mod Warning",
                    description=f"{message.author.mention}, please slow down! You are sending messages too quickly.",
                    color=self.color_warn
                )
                warning_msg = await message.channel.send(embed=warn_embed)
                
                # Delete warning after 5 seconds to keep chat clean
                await asyncio.sleep(5)
                await warning_msg.delete()
            except discord.Forbidden:
                pass # Bot lacks permission to delete

    # ==========================================
    # 👋 2. ADVANCED WELCOME & AUTO-ROLE
    # ==========================================
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # 1. Give Auto-Role immediately
        try:
            role = member.guild.get_role(self.autorole_id)
            if role:
                await member.add_roles(role, reason="Auto-role on join")
        except discord.Forbidden:
            pass # Bot needs "Manage Roles" permission and to be placed above the role

        # 2. Send Welcome Card
        channel = self.bot.get_channel(self.welcome_channel_id)
        if channel: 
            embed = discord.Embed(
                title="👋 Welcome to the Server!",
                description=(
                    f"{member.mention} thanks for joining **{member.guild.name}**!\n\n"
                    f"Visit ➔ <#{self.visit_channel_id}>"
                ),
                color=self.color_main,
                timestamp=discord.utils.utcnow()
            )
            if member.guild.icon:
                embed.set_thumbnail(url=member.guild.icon.url)
            embed.set_footer(text=f"Member #{member.guild.member_count}")
            await channel.send(content=member.mention, embed=embed)

    # ==========================================
    # 🚀 3. BOOST TRACKER
    # ==========================================
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since is None and after.premium_since is not None:
            
            announce_channel = self.bot.get_channel(self.boost_announce_channel_id)
            if announce_channel:
                embed1 = discord.Embed(
                    title="🚀 New Server Booster!",
                    description=f"{after.mention} thanks for boosting you will get\n=> <@&{self.boost_role_id}>",
                    color=self.color_boost
                )
                if after.avatar:
                    embed1.set_thumbnail(url=after.avatar.url)
                await announce_channel.send(content=after.mention, embed=embed1)

            log_channel = self.bot.get_channel(self.boost_log_channel_id)
            if log_channel:
                embed2 = discord.Embed(
                    description=f"{after.mention} got this <@&{self.boost_role_id}> for boosting the server! 🎉",
                    color=self.color_boost
                )
                await log_channel.send(embed=embed2)

    # ==========================================
    # 🗑️ 4. MODERATION COMMANDS (/clear & /nuke)
    # ==========================================
    @app_commands.command(name="clear", description="Bulk delete messages in this channel.")
    @app_commands.describe(amount="Number of messages to delete (max 500)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount > 500:
            embed_limit = discord.Embed(
                description="❌ Can't clear more than **500** messages at once.",
                color=self.color_warn
            )
            return await interaction.response.send_message(embed=embed_limit, ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        
        success_embed = discord.Embed(
            description=f"✅ Successfully cleared **{len(deleted)}** messages.",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=success_embed, ephemeral=True)

    @app_commands.command(name="nuke", description="Clones and deletes the channel to clear all history.")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def nuke(self, interaction: discord.Interaction):
        # A staple command for large servers to instantly reset a chat
        channel = interaction.channel
        await interaction.response.send_message("💣 Nuking channel...", ephemeral=True)
        
        new_channel = await channel.clone(reason=f"Nuked by {interaction.user.name}")
        await channel.delete()
        
        nuke_embed = discord.Embed(
            title="☢️ Channel Nuked",
            description="This channel has been completely reset.",
            color=self.color_warn
        )
        nuke_embed.set_image(url="https://media.giphy.com/media/HhTXt43pk1I1W/giphy.gif") # Aesthetic nuke gif
        await new_channel.send(embed=nuke_embed)

    # ==========================================
    # 🔍 5. ADVANCED LOGGING (Message Deletions)
    # ==========================================
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        log_channel = self.bot.get_channel(self.log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            description=f"**Author:** {message.author.mention}\n**Channel:** {message.channel.mention}",
            color=0x2b2d31,
            timestamp=discord.utils.utcnow()
        )
        # Limit content size in case of huge messages
        content = message.content[:1024] if message.content else "*Message contained no text (image/embed).*"
        embed.add_field(name="Content", value=content, inline=False)
        
        await log_channel.send(embed=embed)

    # ==========================================
    # 🚫 6. DYNAMIC ERROR HANDLER
    # ==========================================
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            missing = ", ".join(error.missing_permissions)
            error_embed = discord.Embed(
                description=f"🚫 {interaction.user.mention} you're lacking permission of `{missing}`",
                color=self.color_warn
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
        else:
            raise error

async def setup(bot):
    await bot.add_cog(ServerCore(bot))
              
