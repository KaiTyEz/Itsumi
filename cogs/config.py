import nextcord
from nextcord.ext import commands
from utils.katlog import logger
from utils.database import db
import asyncio
import time
from typing import Union

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure all necessary database tables exist"""
        try:
            # Anti-link tables
            db.execute("""
                CREATE TABLE IF NOT EXISTS antilink_config (
                    guild_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0
                )
            """)
            
            db.execute("""
                CREATE TABLE IF NOT EXISTS antilink_channels (
                    guild_id TEXT,
                    channel_id TEXT,
                    PRIMARY KEY (guild_id, channel_id)
                )
            """)
            
            db.execute("""
                CREATE TABLE IF NOT EXISTS antilink_violations (
                    guild_id TEXT,
                    user_id TEXT,
                    timestamp REAL,
                    PRIMARY KEY (guild_id, user_id, timestamp)
                )
            """)
            
            # Anti-raid tables
            db.execute("""
                CREATE TABLE IF NOT EXISTS antiraid_config (
                    guild_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    join_threshold INTEGER DEFAULT 5,
                    time_window INTEGER DEFAULT 10,
                    verification_role_id TEXT,
                    verification_channel_id TEXT
                )
            """)
            
            db.execute("""
                CREATE TABLE IF NOT EXISTS antiraid_joins (
                    guild_id TEXT,
                    user_id TEXT,
                    timestamp REAL,
                    verified INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id, timestamp)
                )
            """)
            
            # Anti-nuke tables
            db.execute("""
                CREATE TABLE IF NOT EXISTS antinuke_config (
                    guild_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0
                )
            """)
            
            db.execute("""
                CREATE TABLE IF NOT EXISTS antinuke_thresholds (
                    guild_id TEXT,
                    action TEXT,
                    count INTEGER DEFAULT 3,
                    window INTEGER DEFAULT 10,
                    PRIMARY KEY (guild_id, action)
                )
            """)
            
            db.execute("""
                CREATE TABLE IF NOT EXISTS antinuke_violations (
                    guild_id TEXT,
                    user_id TEXT,
                    action TEXT,
                    timestamp REAL,
                    PRIMARY KEY (guild_id, user_id, action, timestamp)
                )
            """)

            # Anti-spam tables
            db.execute("""
                CREATE TABLE IF NOT EXISTS antispam_config (
                    guild_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    message_rate_limit INTEGER DEFAULT 5,
                    time_window INTEGER DEFAULT 3,
                    max_mentions INTEGER DEFAULT 4,
                    max_repeated_messages INTEGER DEFAULT 3,
                    buffer_time INTEGER DEFAULT 30,
                    warning_expiry INTEGER DEFAULT 3600,
                    log_channel_id TEXT
                )
            """)
            
            db.execute("""
                CREATE TABLE IF NOT EXISTS antispam_whitelist (
                    guild_id TEXT,
                    entity_type TEXT,
                    entity_id TEXT,
                    added_by TEXT,
                    timestamp REAL,
                    PRIMARY KEY (guild_id, entity_type, entity_id)
                )
            """)
            
            # Check and update antiraid_config table if needed
            try:
                # Create a temporary table with the desired schema
                db.execute("""
                    CREATE TABLE IF NOT EXISTS antiraid_config_new (
                        guild_id TEXT PRIMARY KEY,
                        enabled INTEGER DEFAULT 0,
                        join_threshold INTEGER DEFAULT 5,
                        time_window INTEGER DEFAULT 10,
                        verification_role_id TEXT,
                        verification_channel_id TEXT
                    )
                """)
                
                # Copy data from old table to new table
                db.execute("""
                    INSERT OR IGNORE INTO antiraid_config_new (guild_id, enabled)
                    SELECT guild_id, enabled FROM antiraid_config
                """)
                
                # Drop old table and rename new table
                db.execute("DROP TABLE IF EXISTS antiraid_config")
                db.execute("ALTER TABLE antiraid_config_new RENAME TO antiraid_config")
                
            except Exception as e:
                logger.error(f"Error updating antiraid_config table: {e}")
            
            logger.info("Database tables verified successfully")
        except Exception as e:
            logger.error(f"Error ensuring database tables: {e}")

    @commands.group(name="config", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_group(self, ctx: commands.Context):
        """Configuration commands for all protection features"""
        if ctx.invoked_subcommand is None:
            # Show config overview
            guild_id = str(ctx.guild.id)
            
            # Get anti-link config
            antilink_enabled = db.fetch_one(
                "SELECT enabled FROM antilink_config WHERE guild_id = ?",
                (guild_id,)
            )
            antilink_enabled = bool(antilink_enabled[0]) if antilink_enabled else False
            
            antilink_channels = db.fetch_all(
                "SELECT channel_id FROM antilink_channels WHERE guild_id = ?",
                (guild_id,)
            )
            antilink_channel_count = len(antilink_channels)
            
            # Get anti-raid config
            antiraid_config = db.fetch_one(
                "SELECT enabled, join_threshold, time_window FROM antiraid_config WHERE guild_id = ?",
                (guild_id,)
            )
            antiraid_enabled = bool(antiraid_config[0]) if antiraid_config else False
            antiraid_threshold = antiraid_config[1] if antiraid_config else 5
            antiraid_window = antiraid_config[2] if antiraid_config else 10
            
            # Get anti-nuke config
            antinuke_enabled = db.fetch_one(
                "SELECT enabled FROM antinuke_config WHERE guild_id = ?",
                (guild_id,)
            )
            antinuke_enabled = bool(antinuke_enabled[0]) if antinuke_enabled else False
            
            antinuke_thresholds = db.fetch_all(
                "SELECT action, count, window FROM antinuke_thresholds WHERE guild_id = ?",
                (guild_id,)
            )
            
            # Create embed
            embed = nextcord.Embed(
                title=f"Protection Configuration - {ctx.guild.name}",
                color=nextcord.Color.blue()
            )
            
            # Anti-link section
            embed.add_field(
                name="Anti-Link Protection",
                value=f"Status: {'✅ Enabled' if antilink_enabled else '❌ Disabled'}\n"
                      f"Protected Channels: {antilink_channel_count}",
                inline=False
            )
            
            # Anti-raid section
            embed.add_field(
                name="Anti-Raid Protection",
                value=f"Status: {'✅ Enabled' if antiraid_enabled else '❌ Disabled'}\n"
                      f"Join Threshold: {antiraid_threshold} joins\n"
                      f"Time Window: {antiraid_window} seconds",
                inline=False
            )
            
            # Anti-nuke section
            antinuke_text = f"Status: {'✅ Enabled' if antinuke_enabled else '❌ Disabled'}\n"
            if antinuke_thresholds:
                antinuke_text += "Thresholds:\n"
                for action, count, window in antinuke_thresholds:
                    antinuke_text += f"• {action}: {count}/{window}s\n"
            
            embed.add_field(
                name="Anti-Nuke Protection",
                value=antinuke_text,
                inline=False
            )
            
            # Add footer
            embed.set_footer(text="Use the subcommands to configure each protection")
            
            await ctx.send(embed=embed)

    # Anti-Link Configuration Commands
    @config_group.group(name="antilink", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antilink_config(self, ctx: commands.Context):
        """Configure anti-link protection"""
        if ctx.invoked_subcommand is None:
            guild_id = str(ctx.guild.id)
            
            # Get current config
            enabled = db.fetch_one(
                "SELECT enabled FROM antilink_config WHERE guild_id = ?",
                (guild_id,)
            )
            enabled = bool(enabled[0]) if enabled else False
            
            channels = db.fetch_all(
                "SELECT channel_id FROM antilink_channels WHERE guild_id = ?",
                (guild_id,)
            )
            
            # Create embed
            embed = nextcord.Embed(
                title="Anti-Link Configuration",
                color=nextcord.Color.blue()
            )
            
            embed.add_field(
                name="Status",
                value=f"{'✅ Enabled' if enabled else '❌ Disabled'}",
                inline=True
            )
            
            if channels:
                channel_list = ""
                for channel_id in channels:
                    channel = ctx.guild.get_channel(int(channel_id[0]))
                    if channel:
                        channel_list += f"• {channel.mention}\n"
                
                embed.add_field(
                    name="Protected Channels",
                    value=channel_list,
                    inline=False
                )
            else:
                embed.add_field(
                    name="Protected Channels",
                    value="No channels are protected",
                    inline=False
                )
            
            embed.add_field(
                name="Commands",
                value="`config antilink enable` - Enable protection\n"
                      "`config antilink disable` - Disable protection\n"
                      "`config antilink add #channel` - Add a channel\n"
                      "`config antilink remove #channel` - Remove a channel\n"
                      "`config antilink list` - List protected channels",
                inline=False
            )
            
            await ctx.send(embed=embed)

    @antilink_config.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def antilink_enable(self, ctx: commands.Context):
        """Enable anti-link protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "INSERT OR REPLACE INTO antilink_config (guild_id, enabled) VALUES (?, 1)",
            (guild_id,)
        )
        
        await ctx.send("✅ Anti-link protection has been enabled.")

    @antilink_config.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def antilink_disable(self, ctx: commands.Context):
        """Disable anti-link protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antilink_config SET enabled = 0 WHERE guild_id = ?",
            (guild_id,)
        )
        
        await ctx.send("❌ Anti-link protection has been disabled.")

    @antilink_config.command(name="add")
    @commands.has_permissions(administrator=True)
    async def antilink_add(self, ctx: commands.Context, channel: nextcord.TextChannel):
        """Add a channel to anti-link protection"""
        guild_id = str(ctx.guild.id)
        channel_id = str(channel.id)
        
        db.execute(
            "INSERT OR IGNORE INTO antilink_channels (guild_id, channel_id) VALUES (?, ?)",
            (guild_id, channel_id)
        )
        
        await ctx.send(f"✅ {channel.mention} has been added to anti-link protection.")

    @antilink_config.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def antilink_remove(self, ctx: commands.Context, channel: nextcord.TextChannel):
        """Remove a channel from anti-link protection"""
        guild_id = str(ctx.guild.id)
        channel_id = str(channel.id)
        
        db.execute(
            "DELETE FROM antilink_channels WHERE guild_id = ? AND channel_id = ?",
            (guild_id, channel_id)
        )
        
        await ctx.send(f"✅ {channel.mention} has been removed from anti-link protection.")

    @antilink_config.command(name="list")
    @commands.has_permissions(administrator=True)
    async def antilink_list(self, ctx: commands.Context):
        """List all channels with anti-link protection"""
        guild_id = str(ctx.guild.id)
        
        channels = db.fetch_all(
            "SELECT channel_id FROM antilink_channels WHERE guild_id = ?",
            (guild_id,)
        )
        
        if channels:
            channel_list = ""
            for channel_id in channels:
                channel = ctx.guild.get_channel(int(channel_id[0]))
                if channel:
                    channel_list += f"• {channel.mention}\n"
            
            embed = nextcord.Embed(
                title="Anti-Link Protected Channels",
                description=channel_list,
                color=nextcord.Color.blue()
            )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("No channels are currently protected by anti-link.")

    # Anti-Raid Configuration Commands
    @config_group.group(name="antiraid", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antiraid_config(self, ctx: commands.Context):
        """Configure anti-raid protection"""
        if ctx.invoked_subcommand is None:
            guild_id = str(ctx.guild.id)
            
            # Get current config
            config = db.fetch_one(
                "SELECT enabled, join_threshold, time_window FROM antiraid_config WHERE guild_id = ?",
                (guild_id,)
            )
            
            if config:
                enabled = bool(config[0])
                threshold = config[1]
                window = config[2]
                verification_role = ctx.guild.get_role(int(config[3])) if config[3] else None
                verification_channel = ctx.guild.get_channel(int(config[4])) if config[4] else None
            else:
                enabled = False
                threshold = 5
                window = 10
                verification_role = None
                verification_channel = None
            
            # Create embed
            embed = nextcord.Embed(
                title="Anti-Raid Configuration",
                color=nextcord.Color.blue()
            )
            
            embed.add_field(
                name="Status",
                value=f"{'✅ Enabled' if enabled else '❌ Disabled'}",
                inline=True
            )
            
            embed.add_field(
                name="Join Threshold",
                value=f"{threshold} joins",
                inline=True
            )
            
            embed.add_field(
                name="Time Window",
                value=f"{window} seconds",
                inline=True
            )
            
            if verification_role:
                embed.add_field(
                    name="Verification Role",
                    value=verification_role.mention,
                    inline=True
                )
            
            if verification_channel:
                embed.add_field(
                    name="Verification Channel",
                    value=verification_channel.mention,
                    inline=True
                )
            
            embed.add_field(
                name="Commands",
                value="`config antiraid enable` - Enable protection\n"
                      "`config antiraid disable` - Disable protection\n"
                      "`config antiraid threshold <number>` - Set join threshold\n"
                      "`config antiraid window <seconds>` - Set time window\n"
                      "`config antiraid role @role` - Set verification role\n"
                      "`config antiraid channel #channel` - Set verification channel",
                inline=False
            )
            
            await ctx.send(embed=embed)

    @antiraid_config.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def antiraid_enable(self, ctx: commands.Context):
        """Enable anti-raid protection"""
        guild_id = str(ctx.guild.id)
        
        # Check if config exists
        config = db.fetch_one(
            "SELECT * FROM antiraid_config WHERE guild_id = ?",
            (guild_id,)
        )
        
        if config:
            db.execute(
                "UPDATE antiraid_config SET enabled = 1 WHERE guild_id = ?",
                (guild_id,)
            )
        else:
            db.execute(
                "INSERT INTO antiraid_config (guild_id, enabled, join_threshold, time_window) VALUES (?, 1, 5, 10)",
                (guild_id,)
            )
        
        await ctx.send("✅ Anti-raid protection has been enabled.")

    @antiraid_config.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def antiraid_disable(self, ctx: commands.Context):
        """Disable anti-raid protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antiraid_config SET enabled = 0 WHERE guild_id = ?",
            (guild_id,)
        )
        
        await ctx.send("❌ Anti-raid protection has been disabled.")

    @antiraid_config.command(name="threshold")
    @commands.has_permissions(administrator=True)
    async def antiraid_threshold(self, ctx: commands.Context, threshold: int):
        """Set the join threshold for anti-raid protection"""
        if threshold < 2:
            await ctx.send("❌ Threshold must be at least 2 joins.")
            return
        
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antiraid_config SET join_threshold = ? WHERE guild_id = ?",
            (threshold, guild_id)
        )
        
        await ctx.send(f"✅ Join threshold set to {threshold} joins.")

    @antiraid_config.command(name="window")
    @commands.has_permissions(administrator=True)
    async def antiraid_window(self, ctx: commands.Context, seconds: int):
        """Set the time window for anti-raid protection"""
        if seconds < 5:
            await ctx.send("❌ Time window must be at least 5 seconds.")
            return
        
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antiraid_config SET time_window = ? WHERE guild_id = ?",
            (seconds, guild_id)
        )
        
        await ctx.send(f"✅ Time window set to {seconds} seconds.")

    @antiraid_config.command(name="role")
    @commands.has_permissions(administrator=True)
    async def antiraid_role(self, ctx: commands.Context, role: nextcord.Role):
        """Set the verification role for anti-raid protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antiraid_config SET verification_role_id = ? WHERE guild_id = ?",
            (str(role.id), guild_id)
        )
        
        await ctx.send(f"✅ Verification role set to {role.mention}.")

    @antiraid_config.command(name="channel")
    @commands.has_permissions(administrator=True)
    async def antiraid_channel(self, ctx: commands.Context, channel: nextcord.TextChannel):
        """Set the verification channel for anti-raid protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antiraid_config SET verification_channel_id = ? WHERE guild_id = ?",
            (str(channel.id), guild_id)
        )
        
        await ctx.send(f"✅ Verification channel set to {channel.mention}.")

    # Anti-Nuke Configuration Commands
    @config_group.group(name="antinuke", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antinuke_config(self, ctx: commands.Context):
        """Configure anti-nuke protection"""
        if ctx.invoked_subcommand is None:
            guild_id = str(ctx.guild.id)
            
            # Get current config
            enabled = db.fetch_one(
                "SELECT enabled FROM antinuke_config WHERE guild_id = ?",
                (guild_id,)
            )
            enabled = bool(enabled[0]) if enabled else False
            
            thresholds = db.fetch_all(
                "SELECT action, count, window FROM antinuke_thresholds WHERE guild_id = ?",
                (guild_id,)
            )
            
            # Create embed
            embed = nextcord.Embed(
                title="Anti-Nuke Configuration",
                color=nextcord.Color.blue()
            )
            
            embed.add_field(
                name="Status",
                value=f"{'✅ Enabled' if enabled else '❌ Disabled'}",
                inline=True
            )
            
            if thresholds:
                threshold_text = ""
                for action, count, window in thresholds:
                    threshold_text += f"• {action}: {count}/{window}s\n"
                
                embed.add_field(
                    name="Action Thresholds",
                    value=threshold_text,
                    inline=False
                )
            else:
                embed.add_field(
                    name="Action Thresholds",
                    value="No thresholds configured",
                    inline=False
                )
            
            embed.add_field(
                name="Commands",
                value="`config antinuke enable` - Enable protection\n"
                      "`config antinuke disable` - Disable protection\n"
                      "`config antinuke threshold <action> <count> <seconds>` - Set threshold\n"
                      "`config antinuke list` - List all thresholds",
                inline=False
            )
            
            await ctx.send(embed=embed)

    @antinuke_config.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def antinuke_enable(self, ctx: commands.Context):
        """Enable anti-nuke protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "INSERT OR REPLACE INTO antinuke_config (guild_id, enabled) VALUES (?, 1)",
            (guild_id,)
        )
        
        # Set default thresholds if none exist
        default_actions = ['channel_delete', 'role_delete', 'ban', 'kick', 'webhook_create']
        for action in default_actions:
            db.execute(
                """
                INSERT OR IGNORE INTO antinuke_thresholds (guild_id, action, count, window)
                VALUES (?, ?, 3, 10)
                """,
                (guild_id, action)
            )
        
        await ctx.send("✅ Anti-nuke protection has been enabled with default thresholds.")

    @antinuke_config.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def antinuke_disable(self, ctx: commands.Context):
        """Disable anti-nuke protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antinuke_config SET enabled = 0 WHERE guild_id = ?",
            (guild_id,)
        )
        
        await ctx.send("❌ Anti-nuke protection has been disabled.")

    @antinuke_config.command(name="threshold")
    @commands.has_permissions(administrator=True)
    async def antinuke_threshold(self, ctx: commands.Context, action: str, count: int, seconds: int):
        """Set threshold for an anti-nuke action"""
        if count < 1:
            await ctx.send("❌ Count must be at least 1.")
            return
        
        if seconds < 5:
            await ctx.send("❌ Time window must be at least 5 seconds.")
            return
        
        valid_actions = ['channel_delete', 'role_delete', 'ban', 'kick', 'webhook_create']
        if action not in valid_actions:
            await ctx.send(f"❌ Invalid action. Valid actions: {', '.join(valid_actions)}")
            return
        
        guild_id = str(ctx.guild.id)
        
        db.execute(
            """
            INSERT OR REPLACE INTO antinuke_thresholds (guild_id, action, count, window)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, action, count, seconds)
        )
        
        await ctx.send(f"✅ Threshold for {action} set to {count} actions within {seconds} seconds.")

    @antinuke_config.command(name="list")
    @commands.has_permissions(administrator=True)
    async def antinuke_list(self, ctx: commands.Context):
        """List all anti-nuke thresholds"""
        guild_id = str(ctx.guild.id)
        
        thresholds = db.fetch_all(
            "SELECT action, count, window FROM antinuke_thresholds WHERE guild_id = ?",
            (guild_id,)
        )
        
        if thresholds:
            threshold_text = ""
            for action, count, window in thresholds:
                threshold_text += f"• {action}: {count}/{window}s\n"
            
            embed = nextcord.Embed(
                title="Anti-Nuke Thresholds",
                description=threshold_text,
                color=nextcord.Color.blue()
            )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("No thresholds are currently configured for anti-nuke protection.")

    @config_group.group(name="antispam", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antispam_config(self, ctx: commands.Context):
        """Configure anti-spam protection"""
        if ctx.invoked_subcommand is None:
            guild_id = str(ctx.guild.id)
            
            # Get current config
            config = db.fetch_one(
                "SELECT enabled, message_rate_limit, time_window, max_mentions, max_repeated_messages, buffer_time, warning_expiry, log_channel_id FROM antispam_config WHERE guild_id = ?",
                (guild_id,)
            )
            
            if not config:
                config = (0, 5, 3, 4, 3, 30, 3600, None)
            
            enabled, rate_limit, time_window, max_mentions, max_repeated, buffer_time, warning_expiry, log_channel_id = config
            
            # Create embed
            embed = nextcord.Embed(
                title="Anti-Spam Configuration",
                color=nextcord.Color.blue()
            )
            
            embed.add_field(
                name="Status",
                value=f"{'✅ Enabled' if enabled else '❌ Disabled'}",
                inline=True
            )
            
            embed.add_field(
                name="Message Limits",
                value=f"Rate: {rate_limit} messages per {time_window} seconds\n"
                      f"Max Mentions: {max_mentions}\n"
                      f"Max Repeated: {max_repeated}\n"
                      f"Buffer Time: {buffer_time} seconds\n"
                      f"Warning Expiry: {warning_expiry} seconds",
                inline=False
            )
            
            log_channel = ctx.guild.get_channel(int(log_channel_id)) if log_channel_id else None
            embed.add_field(
                name="Log Channel",
                value=log_channel.mention if log_channel else "Not set",
                inline=False
            )
            
            embed.add_field(
                name="Commands",
                value="`config antispam enable` - Enable protection\n"
                      "`config antispam disable` - Disable protection\n"
                      "`config antispam rate <messages> <seconds>` - Set rate limit\n"
                      "`config antispam mentions <number>` - Set mention limit\n"
                      "`config antispam repeated <number>` - Set repeated message limit\n"
                      "`config antispam buffer <seconds>` - Set buffer time\n"
                      "`config antispam expiry <seconds>` - Set warning expiry\n"
                      "`config antispam log #channel` - Set log channel\n"
                      "`config antispam whitelist` - Manage whitelist",
                inline=False
            )
            
            await ctx.send(embed=embed)

    @antispam_config.command(name="enable")
    @commands.has_permissions(administrator=True)
    async def antispam_enable(self, ctx: commands.Context):
        """Enable anti-spam protection"""
        guild_id = str(ctx.guild.id)
        
        # Check if config exists
        config = db.fetch_one(
            "SELECT 1 FROM antispam_config WHERE guild_id = ?",
            (guild_id,)
        )
        
        if not config:
            # Create default config
            db.execute("""
                INSERT INTO antispam_config 
                (guild_id, enabled, message_rate_limit, time_window, max_mentions, max_repeated_messages, buffer_time, warning_expiry)
                VALUES (?, 1, 5, 3, 4, 3, 30, 3600)
            """, (guild_id,))
        else:
            # Enable existing config
            db.execute(
                "UPDATE antispam_config SET enabled = 1 WHERE guild_id = ?",
                (guild_id,)
            )
        
        embed = nextcord.Embed(
            title="✅ Anti-Spam Enabled",
            description="Anti-spam protection has been enabled with default settings.",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @antispam_config.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def antispam_disable(self, ctx: commands.Context):
        """Disable anti-spam protection"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antispam_config SET enabled = 0 WHERE guild_id = ?",
            (guild_id,)
        )
        
        embed = nextcord.Embed(
            title="❌ Anti-Spam Disabled",
            description="Anti-spam protection has been disabled.",
            color=nextcord.Color.red()
        )
        await ctx.send(embed=embed)

    @antispam_config.command(name="rate")
    @commands.has_permissions(administrator=True)
    async def antispam_rate(self, ctx: commands.Context, messages: int, seconds: int):
        """Set message rate limit (messages per seconds)"""
        if messages < 1 or seconds < 1:
            await ctx.send("❌ Values must be positive numbers")
            return
            
        guild_id = str(ctx.guild.id)
        
        db.execute("""
            UPDATE antispam_config 
            SET message_rate_limit = ?, time_window = ?
            WHERE guild_id = ?
        """, (messages, seconds, guild_id))
        
        embed = nextcord.Embed(
            title="✅ Rate Limit Updated",
            description=f"Set to {messages} messages per {seconds} seconds",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @antispam_config.command(name="mentions")
    @commands.has_permissions(administrator=True)
    async def antispam_mentions(self, ctx: commands.Context, limit: int):
        """Set maximum mentions per message"""
        if limit < 1:
            await ctx.send("❌ Value must be a positive number")
            return
            
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antispam_config SET max_mentions = ? WHERE guild_id = ?",
            (limit, guild_id)
        )
        
        embed = nextcord.Embed(
            title="✅ Mention Limit Updated",
            description=f"Maximum mentions per message set to {limit}",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @antispam_config.command(name="repeated")
    @commands.has_permissions(administrator=True)
    async def antispam_repeated(self, ctx: commands.Context, limit: int):
        """Set maximum repeated messages"""
        if limit < 1:
            await ctx.send("❌ Value must be a positive number")
            return
            
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antispam_config SET max_repeated_messages = ? WHERE guild_id = ?",
            (limit, guild_id)
        )
        
        embed = nextcord.Embed(
            title="✅ Repeated Message Limit Updated",
            description=f"Maximum repeated messages set to {limit}",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @antispam_config.command(name="buffer")
    @commands.has_permissions(administrator=True)
    async def antispam_buffer(self, ctx: commands.Context, seconds: int):
        """Set message buffer time"""
        if seconds < 1:
            await ctx.send("❌ Value must be a positive number")
            return
            
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antispam_config SET buffer_time = ? WHERE guild_id = ?",
            (seconds, guild_id)
        )
        
        embed = nextcord.Embed(
            title="✅ Buffer Time Updated",
            description=f"Message buffer time set to {seconds} seconds",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @antispam_config.command(name="expiry")
    @commands.has_permissions(administrator=True)
    async def antispam_expiry(self, ctx: commands.Context, seconds: int):
        """Set warning expiry time"""
        if seconds < 1:
            await ctx.send("❌ Value must be a positive number")
            return
            
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antispam_config SET warning_expiry = ? WHERE guild_id = ?",
            (seconds, guild_id)
        )
        
        embed = nextcord.Embed(
            title="✅ Warning Expiry Updated",
            description=f"Warning expiry time set to {seconds} seconds",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @antispam_config.command(name="log")
    @commands.has_permissions(administrator=True)
    async def antispam_log(self, ctx: commands.Context, channel: nextcord.TextChannel):
        """Set log channel for anti-spam events"""
        guild_id = str(ctx.guild.id)
        
        db.execute(
            "UPDATE antispam_config SET log_channel_id = ? WHERE guild_id = ?",
            (str(channel.id), guild_id)
        )
        
        embed = nextcord.Embed(
            title="✅ Log Channel Updated",
            description=f"Anti-spam logs will be sent to {channel.mention}",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @antispam_config.group(name="whitelist", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def antispam_whitelist(self, ctx: commands.Context):
        """Manage anti-spam whitelist"""
        if ctx.invoked_subcommand is None:
            guild_id = str(ctx.guild.id)
            
            whitelist = db.fetch_all(
                "SELECT entity_type, entity_id FROM antispam_whitelist WHERE guild_id = ?",
                (guild_id,)
            )
            
            if not whitelist:
                embed = nextcord.Embed(
                    title="Anti-Spam Whitelist",
                    description="The whitelist is empty.",
                    color=nextcord.Color.blue()
                )
                embed.add_field(
                    name="Commands",
                    value="`config antispam whitelist add @user/@role/#channel` - Add to whitelist\n"
                          "`config antispam whitelist remove @user/@role/#channel` - Remove from whitelist",
                    inline=False
                )
                return await ctx.send(embed=embed)
            
            users = []
            roles = []
            channels = []
            
            for entity_type, entity_id in whitelist:
                if entity_type == 'user':
                    user = ctx.guild.get_member(int(entity_id))
                    if user:
                        users.append(f"• {user.mention} ({user.id})")
                elif entity_type == 'role':
                    role = ctx.guild.get_role(int(entity_id))
                    if role:
                        roles.append(f"• {role.mention} ({role.id})")
                elif entity_type == 'channel':
                    channel = ctx.guild.get_channel(int(entity_id))
                    if channel:
                        channels.append(f"• {channel.mention} ({channel.id})")
            
            embed = nextcord.Embed(
                title="Anti-Spam Whitelist",
                color=nextcord.Color.blue()
            )
            
            if users:
                embed.add_field(name="Whitelisted Users", value="\n".join(users), inline=False)
            if roles:
                embed.add_field(name="Whitelisted Roles", value="\n".join(roles), inline=False)
            if channels:
                embed.add_field(name="Whitelisted Channels", value="\n".join(channels), inline=False)
            
            embed.add_field(
                name="Commands",
                value="`config antispam whitelist add @user/@role/#channel` - Add to whitelist\n"
                      "`config antispam whitelist remove @user/@role/#channel` - Remove from whitelist",
                inline=False
            )
            
            await ctx.send(embed=embed)

    @antispam_whitelist.command(name="add")
    @commands.has_permissions(administrator=True)
    async def antispam_whitelist_add(self, ctx: commands.Context, target: Union[nextcord.Member, nextcord.Role, nextcord.TextChannel]):
        """Add a user, role, or channel to the anti-spam whitelist"""
        guild_id = str(ctx.guild.id)
        
        if isinstance(target, nextcord.Member):
            entity_type = 'user'
            entity_id = str(target.id)
            name = f"{target.display_name} (User)"
        elif isinstance(target, nextcord.Role):
            entity_type = 'role'
            entity_id = str(target.id)
            name = f"{target.name} (Role)"
        elif isinstance(target, nextcord.TextChannel):
            entity_type = 'channel'
            entity_id = str(target.id)
            name = f"{target.name} (Channel)"
        else:
            await ctx.send("❌ Invalid target. Please mention a user, role, or channel.")
            return
        
        db.execute("""
            INSERT OR REPLACE INTO antispam_whitelist 
            (guild_id, entity_type, entity_id, added_by, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (guild_id, entity_type, entity_id, str(ctx.author.id), time.time()))
        
        embed = nextcord.Embed(
            title="✅ Whitelist Updated",
            description=f"Added {name} to the anti-spam whitelist.",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @antispam_whitelist.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def antispam_whitelist_remove(self, ctx: commands.Context, target: Union[nextcord.Member, nextcord.Role, nextcord.TextChannel]):
        """Remove a user, role, or channel from the anti-spam whitelist"""
        guild_id = str(ctx.guild.id)
        
        if isinstance(target, nextcord.Member):
            entity_type = 'user'
            entity_id = str(target.id)
            name = f"{target.display_name} (User)"
        elif isinstance(target, nextcord.Role):
            entity_type = 'role'
            entity_id = str(target.id)
            name = f"{target.name} (Role)"
        elif isinstance(target, nextcord.TextChannel):
            entity_type = 'channel'
            entity_id = str(target.id)
            name = f"{target.name} (Channel)"
        else:
            await ctx.send("❌ Invalid target. Please mention a user, role, or channel.")
            return
        
        db.execute("""
            DELETE FROM antispam_whitelist 
            WHERE guild_id = ? AND entity_type = ? AND entity_id = ?
        """, (guild_id, entity_type, entity_id))
        
        embed = nextcord.Embed(
            title="✅ Whitelist Updated",
            description=f"Removed {name} from the anti-spam whitelist.",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_protection(self, ctx: commands.Context):
        """Set up all protection features with recommended settings"""
        guild_id = str(ctx.guild.id)
        
        # Enable anti-link
        db.execute(
            "INSERT OR REPLACE INTO antilink_config (guild_id, enabled) VALUES (?, 1)",
            (guild_id,)
        )
        
        # Enable anti-raid with default settings
        db.execute("""
            INSERT OR REPLACE INTO antiraid_config 
            (guild_id, enabled, join_threshold, time_window)
            VALUES (?, 1, 5, 10)
        """, (guild_id,))
        
        # Enable anti-nuke
        db.execute(
            "INSERT OR REPLACE INTO antinuke_config (guild_id, enabled) VALUES (?, 1)",
            (guild_id,)
        )
        
        # Set default anti-nuke thresholds
        default_thresholds = [
            ('ban', 3, 10),
            ('kick', 3, 10),
            ('role_create', 3, 10),
            ('role_delete', 3, 10),
            ('channel_create', 3, 10),
            ('channel_delete', 3, 10),
            ('webhook_create', 3, 10)
        ]
        
        for action, count, window in default_thresholds:
            db.execute("""
                INSERT OR REPLACE INTO antinuke_thresholds 
                (guild_id, action, count, window)
                VALUES (?, ?, ?, ?)
            """, (guild_id, action, count, window))
        
        # Enable anti-spam with default settings
        db.execute("""
            INSERT OR REPLACE INTO antispam_config 
            (guild_id, enabled, message_rate_limit, time_window, max_mentions, max_repeated_messages, buffer_time, warning_expiry)
            VALUES (?, 1, 5, 3, 4, 3, 30, 3600)
        """, (guild_id,))
        
        # Create embed with setup summary
        embed = nextcord.Embed(
            title="🛡️ Protection Setup Complete",
            description="All protection features have been enabled with recommended settings.",
            color=nextcord.Color.green()
        )
        
        embed.add_field(
            name="Anti-Link",
            value="✅ Enabled\nProtected channels can be added with `config antilink add #channel`",
            inline=False
        )
        
        embed.add_field(
            name="Anti-Raid",
            value="✅ Enabled\n• 5 joins per 10 seconds\n• Verification system ready\nUse `config antiraid` to customize",
            inline=False
        )
        
        embed.add_field(
            name="Anti-Nuke",
            value="✅ Enabled\n• 3 actions per 10 seconds for all operations\nUse `config antinuke` to customize",
            inline=False
        )
        
        embed.add_field(
            name="Anti-Spam",
            value="✅ Enabled\n• 5 messages per 3 seconds\n• 4 max mentions\n• 3 repeated messages\n• 30s buffer time\nUse `config antispam` to customize",
            inline=False
        )
        
        embed.add_field(
            name="Next Steps",
            value="1. Set up log channels for each system\n"
                  "2. Add protected channels for anti-link\n"
                  "3. Configure verification role/channel for anti-raid\n"
                  "4. Customize thresholds if needed",
            inline=False
        )
        
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(ConfigCog(bot)) 