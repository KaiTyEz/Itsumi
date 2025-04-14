import nextcord
from nextcord.ext import commands
import re
from utils.katlog import logger
from utils.database import db
import time

class AntiLink(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.link_patterns = [
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,6}(?:/[^\\s]*)?',
            r'(?:discord\.gg|discord\.com/invite)/[a-zA-Z0-9]+'
        ]
        self.compiled_patterns = [re.compile(pattern) for pattern in self.link_patterns]

    def is_enabled(self, guild_id: str) -> bool:
        """Check if anti-link is enabled for a guild"""
        result = db.fetch_one(
            "SELECT enabled FROM antilink_config WHERE guild_id = ?",
            (guild_id,)
        )
        return bool(result[0]) if result else False

    def is_channel_protected(self, guild_id: str, channel_id: str) -> bool:
        """Check if a channel is protected by anti-link"""
        result = db.fetch_one(
            "SELECT 1 FROM antilink_channels WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        return bool(result)

    def get_violation_count(self, user_id: str, guild_id: str) -> int:
        """Get the violation count for a user"""
        result = db.fetch_one(
            "SELECT count FROM antilink_violations WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        return result[0] if result else 0

    def increment_violation(self, user_id: str, guild_id: str):
        """Increment the violation count for a user"""
        current_time = time.time()
        db.execute(
            """
            INSERT INTO antilink_violations (user_id, guild_id, count, last_violation)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
            count = count + 1,
            last_violation = ?
            """,
            (user_id, guild_id, current_time, current_time)
        )

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        if message.author.bot:
            return

        guild_id = str(message.guild.id)
        if not self.is_enabled(guild_id):
            return

        channel_id = str(message.channel.id)
        if not self.is_channel_protected(guild_id, channel_id):
            return

        for pattern in self.compiled_patterns:
            if pattern.search(message.content):
                try:
                    # Level 1: Delete message and warn
                    await message.delete()
                    await message.channel.send(
                        f"{message.author.mention} Please don't send links in this channel! (Level 1)",
                        delete_after=10
                    )
                    logger.info(f"Anti-link triggered by {message.author} in {message.channel.name}")
                    
                    # Track violations
                    user_id = str(message.author.id)
                    self.increment_violation(user_id, guild_id)
                    violation_count = self.get_violation_count(user_id, guild_id)
                    
                    # Level 2: Add timeout if multiple violations
                    if violation_count >= 3:
                        try:
                            await message.author.timeout(duration=300, reason="Multiple link violations")
                            await message.channel.send(
                                f"{message.author.mention} has been timed out for 5 minutes due to multiple link violations.",
                                delete_after=10
                            )
                        except nextcord.Forbidden:
                            logger.error(f"Failed to timeout user {message.author} - Missing permissions")
                    
                    # Level 3: Ban if severe violations
                    if violation_count >= 5:
                        try:
                            await message.author.ban(reason="Severe link violations")
                            await message.channel.send(
                                f"{message.author.mention} has been banned for severe link violations.",
                                delete_after=10
                            )
                        except nextcord.Forbidden:
                            logger.error(f"Failed to ban user {message.author} - Missing permissions")
                    
                except nextcord.Forbidden:
                    logger.error(f"Failed to delete message in {message.channel.name} - Missing permissions")
                except Exception as e:
                    logger.error(f"Error in anti-link protection: {e}")

    @commands.group(name="antilink", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antilink_group(self, ctx: commands.Context):
        """Anti-link protection commands"""
        if ctx.invoked_subcommand is None:
            guild_id = str(ctx.guild.id)
            if self.is_enabled(guild_id):
                channels = db.fetch_all(
                    "SELECT channel_id FROM antilink_channels WHERE guild_id = ?",
                    (guild_id,)
                )
                channel_mentions = [ctx.guild.get_channel(int(channel_id[0])).mention for channel_id in channels]
                await ctx.send(f"Anti-link protection is enabled in: {', '.join(channel_mentions)}")
            else:
                await ctx.send("Anti-link protection is disabled. Use `antilink enable` to enable it.")

    @antilink_group.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def antilink_enable(self, ctx: commands.Context, channel: nextcord.TextChannel = None):
        """Enable anti-link protection in a channel"""
        guild_id = str(ctx.guild.id)
        
        # Enable anti-link for the guild if not already enabled
        db.execute(
            "INSERT OR IGNORE INTO antilink_config (guild_id, enabled) VALUES (?, 1)",
            (guild_id,)
        )
        
        channel_id = str(channel.id if channel else ctx.channel.id)
        db.execute(
            "INSERT OR IGNORE INTO antilink_channels (guild_id, channel_id) VALUES (?, ?)",
            (guild_id, channel_id)
        )
        
        await ctx.send(f"Anti-link protection enabled in {channel.mention if channel else ctx.channel.mention}")

    @antilink_group.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def antilink_disable(self, ctx: commands.Context, channel: nextcord.TextChannel = None):
        """Disable anti-link protection in a channel"""
        guild_id = str(ctx.guild.id)
        
        if channel:
            channel_id = str(channel.id)
            db.execute(
                "DELETE FROM antilink_channels WHERE guild_id = ? AND channel_id = ?",
                (guild_id, channel_id)
            )
            await ctx.send(f"Anti-link protection disabled in {channel.mention}")
        else:
            db.execute(
                "DELETE FROM antilink_channels WHERE guild_id = ?",
                (guild_id,)
            )
            db.execute(
                "UPDATE antilink_config SET enabled = 0 WHERE guild_id = ?",
                (guild_id,)
            )
            await ctx.send("Anti-link protection disabled for all channels")

    @antilink_group.command(name="status")
    @commands.has_permissions(administrator=True)
    async def antilink_status(self, ctx: commands.Context):
        """Check anti-link protection status"""
        guild_id = str(ctx.guild.id)
        if self.is_enabled(guild_id):
            channels = db.fetch_all(
                "SELECT channel_id FROM antilink_channels WHERE guild_id = ?",
                (guild_id,)
            )
            channel_mentions = [ctx.guild.get_channel(int(channel_id[0])).mention for channel_id in channels]
            
            violations = db.fetch_all(
                "SELECT user_id, count FROM antilink_violations WHERE guild_id = ? ORDER BY count DESC LIMIT 5",
                (guild_id,)
            )
            
            embed = nextcord.Embed(
                title="Anti-Link Protection Status",
                color=nextcord.Color.blue()
            )
            embed.add_field(name="Status", value="✅ Enabled", inline=True)
            embed.add_field(name="Protected Channels", value="\n".join(channel_mentions) if channel_mentions else "None", inline=False)
            
            if violations:
                violation_text = "\n".join([f"<@{v[0]}>: {v[1]} violations" for v in violations])
                embed.add_field(name="Top Violators", value=violation_text, inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("Anti-link protection is disabled.")

def setup(bot):
    bot.add_cog(AntiLink(bot)) 