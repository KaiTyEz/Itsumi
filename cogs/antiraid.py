import nextcord
from nextcord.ext import commands
from collections import defaultdict
import asyncio
from utils.katlog import logger
import time
from utils.database import db

class AntiRaid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_enabled(self, guild_id: str) -> bool:
        """Check if anti-raid is enabled for a guild"""
        result = db.fetch_one(
            "SELECT enabled FROM antiraid_config WHERE guild_id = ?",
            (guild_id,)
        )
        return bool(result[0]) if result else False

    def get_config(self, guild_id: str) -> dict:
        """Get anti-raid configuration for a guild"""
        result = db.fetch_one(
            """
            SELECT enabled, verification_required, raid_threshold, time_window, verification_timeout
            FROM antiraid_config WHERE guild_id = ?
            """,
            (guild_id,)
        )
        if result:
            return {
                'enabled': bool(result[0]),
                'verification_required': bool(result[1]),
                'raid_threshold': result[2],
                'time_window': result[3],
                'verification_timeout': result[4]
            }
        return {
            'enabled': False,
            'verification_required': True,
            'raid_threshold': 5,
            'time_window': 10,
            'verification_timeout': 300
        }

    def add_join_time(self, guild_id: str, timestamp: float):
        """Add a join time to the database"""
        db.execute(
            "INSERT INTO antiraid_joins (guild_id, timestamp) VALUES (?, ?)",
            (guild_id, timestamp)
        )

    def get_recent_joins(self, guild_id: str, time_window: int) -> list:
        """Get recent joins within the time window"""
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        db.execute(
            "DELETE FROM antiraid_joins WHERE guild_id = ? AND timestamp < ?",
            (guild_id, cutoff_time)
        )
        
        return db.fetch_all(
            "SELECT timestamp FROM antiraid_joins WHERE guild_id = ? AND timestamp >= ?",
            (guild_id, cutoff_time)
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: nextcord.Member):
        guild_id = str(member.guild.id)
        config = self.get_config(guild_id)
        
        if not config['enabled']:
            return

        current_time = time.time()
        self.add_join_time(guild_id, current_time)
        
        # Check for raid pattern
        recent_joins = self.get_recent_joins(guild_id, config['time_window'])
        if len(recent_joins) >= config['raid_threshold']:
            await this.handle_raid_detection(member.guild)
        
        # Apply verification if enabled
        if config['verification_required']:
            await this.apply_verification(member)

    async def handle_raid_detection(self, guild: nextcord.Guild):
        try:
            guild_id = str(guild.id)
            
            # Enable verification
            db.execute(
                "UPDATE antiraid_config SET verification_required = 1 WHERE guild_id = ?",
                (guild_id,)
            )
            
            # Log the raid detection
            logger.warning(f"Raid detected in {guild.name}! Enabling verification.")
            
            # Notify server staff
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    await channel.send(
                        "🚨 **RAID DETECTED** 🚨\n"
                        "Verification has been enabled. New members will need to verify.",
                        delete_after=30
                    )
                    break
            
        except Exception as e:
            logger.error(f"Error in raid detection handling: {e}")

    async def apply_verification(self, member: nextcord.Member):
        try:
            guild_id = str(member.guild.id)
            config = self.get_config(guild_id)
            
            # Create a verification role if it doesn't exist
            verification_role = nextcord.utils.get(member.guild.roles, name="Verification")
            if not verification_role:
                verification_role = await member.guild.create_role(
                    name="Verification",
                    color=nextcord.Color.blue(),
                    reason="Anti-raid protection"
                )
            
            # Assign verification role
            await member.add_roles(verification_role)
            
            # DM the user with verification instructions
            try:
                await member.send(
                    "Welcome to the server! Please verify yourself to access the server.\n"
                    f"You have {config['verification_timeout'] // 60} minutes to verify or you will be kicked."
                )
            except nextcord.Forbidden:
                pass  # User might have DMs disabled
            
            # Set up verification timeout
            await asyncio.sleep(config['verification_timeout'])
            
            # Check if user still has verification role
            if verification_role in member.roles:
                await member.kick(reason="Failed to verify within time limit")
                logger.info(f"Kicked {member} for failing to verify")
                
        except Exception as e:
            logger.error(f"Error applying verification to {member}: {e}")

    @commands.group(name="antiraid", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antiraid_group(self, ctx: commands.Context):
        """Anti-raid protection commands"""
        if ctx.invoked_subcommand is None:
            guild_id = str(ctx.guild.id)
            config = self.get_config(guild_id)
            
            if config['enabled']:
                recent_joins = self.get_recent_joins(guild_id, config['time_window'])
                
                embed = nextcord.Embed(
                    title="Anti-Raid Protection Status",
                    color=nextcord.Color.blue()
                )
                embed.add_field(name="Status", value="✅ Enabled", inline=True)
                embed.add_field(name="Verification Required", value="✅" if config['verification_required'] else "❌", inline=True)
                embed.add_field(name="Raid Threshold", value=str(config['raid_threshold']), inline=True)
                embed.add_field(name="Time Window", value=f"{config['time_window']} seconds", inline=True)
                embed.add_field(name="Recent Joins", value=str(len(recent_joins)), inline=True)
                await ctx.send(embed=embed)
            else:
                await ctx.send("Anti-raid protection is disabled. Use `antiraid enable` to enable it.")

    @antiraid_group.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def antiraid_enable(self, ctx: commands.Context):
        """Enable anti-raid protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            """
            INSERT INTO antiraid_config 
            (guild_id, enabled, verification_required, raid_threshold, time_window, verification_timeout)
            VALUES (?, 1, 1, 5, 10, 300)
            ON CONFLICT(guild_id) DO UPDATE SET enabled = 1
            """,
            (guild_id,)
        )
        
        await ctx.send("Anti-raid protection has been enabled.")

    @antiraid_group.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def antiraid_disable(self, ctx: commands.Context):
        """Disable anti-raid protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antiraid_config SET enabled = 0 WHERE guild_id = ?",
            (guild_id,)
        )
        
        await ctx.send("Anti-raid protection has been disabled.")

    @antiraid_group.command(name="config")
    @commands.has_permissions(administrator=True)
    async def antiraid_config(self, ctx: commands.Context, threshold: int = None, time_window: int = None, verification_timeout: int = None):
        """Configure anti-raid protection settings"""
        guild_id = str(ctx.guild.id)
        
        if threshold is not None:
            threshold = max(1, min(threshold, 20))
            db.execute(
                "UPDATE antiraid_config SET raid_threshold = ? WHERE guild_id = ?",
                (threshold, guild_id)
            )
        
        if time_window is not None:
            time_window = max(5, min(time_window, 60))
            db.execute(
                "UPDATE antiraid_config SET time_window = ? WHERE guild_id = ?",
                (time_window, guild_id)
            )
        
        if verification_timeout is not None:
            verification_timeout = max(60, min(verification_timeout, 3600))
            db.execute(
                "UPDATE antiraid_config SET verification_timeout = ? WHERE guild_id = ?",
                (verification_timeout, guild_id)
            )
        
        config = self.get_config(guild_id)
        
        embed = nextcord.Embed(
            title="Anti-Raid Configuration Updated",
            color=nextcord.Color.green()
        )
        embed.add_field(name="Raid Threshold", value=str(config['raid_threshold']), inline=True)
        embed.add_field(name="Time Window", value=f"{config['time_window']} seconds", inline=True)
        embed.add_field(name="Verification Timeout", value=f"{config['verification_timeout'] // 60} minutes", inline=True)
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(AntiRaid(bot)) 