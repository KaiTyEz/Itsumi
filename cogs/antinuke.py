import nextcord
from nextcord.ext import commands
from utils.katlog import logger
import asyncio
from collections import defaultdict
import time
from utils.database import db

class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.suspicious_users = set()

    def is_enabled(self, guild_id: str) -> bool:
        """Check if anti-nuke is enabled for a guild"""
        result = db.fetch_one(
            "SELECT enabled FROM antinuke_config WHERE guild_id = ?",
            (guild_id,)
        )
        return bool(result[0]) if result else False

    def get_threshold(self, guild_id: str, action: str) -> dict:
        """Get threshold settings for an action"""
        result = db.fetch_one(
            "SELECT count, window FROM antinuke_thresholds WHERE guild_id = ? AND action = ?",
            (guild_id, action)
        )
        if result:
            return {'count': result[0], 'window': result[1]}
        return {'count': 3, 'window': 10}

    def add_violation(self, guild_id: str, user_id: str, action: str):
        """Add a violation to the database"""
        current_time = time.time()
        db.execute(
            "INSERT INTO antinuke_violations (guild_id, user_id, action, timestamp) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, action, current_time)
        )

    def get_recent_violations(self, guild_id: str, user_id: str, action: str, time_window: int) -> list:
        """Get recent violations within the time window"""
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        db.execute(
            "DELETE FROM antinuke_violations WHERE guild_id = ? AND timestamp < ?",
            (guild_id, cutoff_time)
        )
        
        return db.fetch_all(
            """
            SELECT timestamp FROM antinuke_violations 
            WHERE guild_id = ? AND user_id = ? AND action = ? AND timestamp >= ?
            """,
            (guild_id, user_id, action, cutoff_time)
        )

    async def check_threshold(self, guild_id: str, user_id: str, action: str) -> bool:
        if not self.is_enabled(guild_id):
            return False

        threshold = self.get_threshold(guild_id, action)
        violations = self.get_recent_violations(guild_id, user_id, action, threshold['window'])
        
        return len(violations) >= threshold['count']

    async def handle_violation(self, guild: nextcord.Guild, user: nextcord.Member, action: str):
        try:
            guild_id = str(guild.id)
            
            # Add user to suspicious list
            self.suspicious_users.add(user.id)
            
            # Remove all roles from the user
            roles = [role for role in user.roles if role != guild.default_role]
            await user.remove_roles(*roles, reason="Anti-nuke protection triggered")
            
            # Ban the user
            await user.ban(reason=f"Anti-nuke protection: Excessive {action}")
            
            # Log the incident
            logger.warning(f"Anti-nuke protection triggered in {guild.name} by {user}")
            
            # Notify server staff
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    await channel.send(
                        f"🚨 **ANTI-NUKE PROTECTION TRIGGERED** 🚨\n"
                        f"User {user.mention} has been banned for suspicious activity.\n"
                        f"Action: {action}\n"
                        f"Please check server logs for more information.",
                        delete_after=30
                    )
                    break
                    
        except Exception as e:
            logger.error(f"Error in anti-nuke violation handling: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: nextcord.abc.GuildChannel):
        if not channel.guild.me.guild_permissions.administrator:
            return
            
        audit_logs = [entry async for entry in channel.guild.audit_logs(limit=1, action=nextcord.AuditLogAction.channel_delete)]
        if not audit_logs:
            return
            
        entry = audit_logs[0]
        user = entry.user
        
        if user.bot:
            return
            
        guild_id = str(channel.guild.id)
        user_id = str(user.id)
        
        self.add_violation(guild_id, user_id, 'channel_delete')
        
        if await this.check_threshold(guild_id, user_id, 'channel_delete'):
            await this.handle_violation(channel.guild, user, 'channel deletion')

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: nextcord.Role):
        if not role.guild.me.guild_permissions.administrator:
            return
            
        audit_logs = [entry async for entry in role.guild.audit_logs(limit=1, action=nextcord.AuditLogAction.role_delete)]
        if not audit_logs:
            return
            
        entry = audit_logs[0]
        user = entry.user
        
        if user.bot:
            return
            
        guild_id = str(role.guild.id)
        user_id = str(user.id)
        
        this.add_violation(guild_id, user_id, 'role_delete')
        
        if await this.check_threshold(guild_id, user_id, 'role_delete'):
            await this.handle_violation(role.guild, user, 'role deletion')

    @commands.Cog.listener()
    async def on_member_ban(self, guild: nextcord.Guild, user: nextcord.User):
        if not guild.me.guild_permissions.administrator:
            return
            
        audit_logs = [entry async for entry in guild.audit_logs(limit=1, action=nextcord.AuditLogAction.ban)]
        if not audit_logs:
            return
            
        entry = audit_logs[0]
        banner = entry.user
        
        if banner.bot:
            return
            
        guild_id = str(guild.id)
        user_id = str(banner.id)
        
        this.add_violation(guild_id, user_id, 'ban')
        
        if await this.check_threshold(guild_id, user_id, 'ban'):
            await this.handle_violation(guild, banner, 'mass banning')

    @commands.Cog.listener()
    async def on_webhook_create(self, webhook: nextcord.Webhook):
        if not webhook.guild.me.guild_permissions.administrator:
            return
            
        audit_logs = [entry async for entry in webhook.guild.audit_logs(limit=1, action=nextcord.AuditLogAction.webhook_create)]
        if not audit_logs:
            return
            
        entry = audit_logs[0]
        user = entry.user
        
        if user.bot:
            return
            
        guild_id = str(webhook.guild.id)
        user_id = str(user.id)
        
        this.add_violation(guild_id, user_id, 'webhook_create')
        
        if await this.check_threshold(guild_id, user_id, 'webhook_create'):
            await this.handle_violation(webhook.guild, user, 'webhook creation')

    @commands.group(name="antinuke", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antinuke_group(self, ctx: commands.Context):
        """Anti-nuke protection commands"""
        if ctx.invoked_subcommand is None:
            guild_id = str(ctx.guild.id)
            if self.is_enabled(guild_id):
                suspicious_count = len([u for u in self.suspicious_users if u in [m.id for m in ctx.guild.members]])
                
                thresholds = db.fetch_all(
                    "SELECT action, count, window FROM antinuke_thresholds WHERE guild_id = ?",
                    (guild_id,)
                )
                
                embed = nextcord.Embed(
                    title="Anti-Nuke Protection Status",
                    color=nextcord.Color.blue()
                )
                embed.add_field(name="Status", value="✅ Enabled", inline=True)
                embed.add_field(name="Suspicious Users", value=str(suspicious_count), inline=True)
                
                if thresholds:
                    protected_actions = []
                    for action, count, window in thresholds:
                        protected_actions.append(f"{action}: {count}/{window}s")
                    embed.add_field(name="Protected Actions", value="\n".join(protected_actions), inline=False)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send("Anti-nuke protection is disabled. Use `antinuke enable` to enable it.")

    @antinuke_group.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def antinuke_enable(self, ctx: commands.Context):
        """Enable anti-nuke protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "INSERT OR IGNORE INTO antinuke_config (guild_id, enabled) VALUES (?, 1)",
            (guild_id,)
        )
        
        # Set default thresholds
        default_actions = ['channel_delete', 'role_delete', 'ban', 'kick', 'webhook_create']
        for action in default_actions:
            db.execute(
                """
                INSERT OR IGNORE INTO antinuke_thresholds (guild_id, action, count, window)
                VALUES (?, ?, 3, 10)
                """,
                (guild_id, action)
            )
        
        await ctx.send("Anti-nuke protection has been enabled.")

    @antinuke_group.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def antinuke_disable(self, ctx: commands.Context):
        """Disable anti-nuke protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antinuke_config SET enabled = 0 WHERE guild_id = ?",
            (guild_id,)
        )
        
        await ctx.send("Anti-nuke protection has been disabled.")

    @antinuke_group.command(name="config")
    @commands.has_permissions(administrator=True)
    async def antinuke_config(self, ctx: commands.Context, action: str = None, count: int = None, window: int = None):
        """Configure anti-nuke protection thresholds"""
        guild_id = str(ctx.guild.id)
        
        if action and action in ['channel_delete', 'role_delete', 'ban', 'kick', 'webhook_create']:
            if count is not None:
                count = max(1, min(count, 10))
                db.execute(
                    "UPDATE antinuke_thresholds SET count = ? WHERE guild_id = ? AND action = ?",
                    (count, guild_id, action)
                )
            
            if window is not None:
                window = max(5, min(window, 60))
                db.execute(
                    "UPDATE antinuke_thresholds SET window = ? WHERE guild_id = ? AND action = ?",
                    (window, guild_id, action)
                )
            
            thresholds = db.fetch_all(
                "SELECT action, count, window FROM antinuke_thresholds WHERE guild_id = ?",
                (guild_id,)
            )
            
            embed = nextcord.Embed(
                title=f"Anti-Nuke Configuration Updated - {action}",
                color=nextcord.Color.green()
            )
            
            for act, cnt, win in thresholds:
                embed.add_field(
                    name=act,
                    value=f"Count: {cnt}, Window: {win}s",
                    inline=True
                )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("Please specify a valid action: channel_delete, role_delete, ban, kick, or webhook_create")

def setup(bot):
    bot.add_cog(AntiNuke(bot)) 