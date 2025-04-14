import nextcord
from nextcord.ext import commands
import asyncio
import datetime
import sqlite3
import os
import time
from typing import Dict, List, Optional, Union

class SpamDatabase:
    def __init__(self, db_path="db/security.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()
        
    def _create_tables(self):
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_history (
            user_id INTEGER,
            guild_id INTEGER,
            channel_id INTEGER,
            message_id INTEGER,
            content TEXT,
            timestamp REAL,
            PRIMARY KEY (user_id, message_id)
        )''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            user_id INTEGER,
            guild_id INTEGER,
            warning_type TEXT,
            timestamp REAL,
            expires_at REAL,
            warned_by INTEGER
        )''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS punishments (
            user_id INTEGER,
            guild_id INTEGER,
            punishment_type TEXT,
            reason TEXT,
            timestamp REAL,
            duration REAL,
            expires_at REAL,
            applied_by INTEGER
        )''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            config_json TEXT
        )''')


        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS whitelist (
            guild_id INTEGER,
            entity_type TEXT,
            entity_id INTEGER,
            added_by INTEGER,
            timestamp REAL,
            PRIMARY KEY (guild_id, entity_type, entity_id)
        )''')
        
        
        self.conn.commit()


    def add_to_whitelist(self, guild_id, entity_type, entity_id, added_by):
        """Add an entity to the whitelist
        entity_type can be 'user', 'role', or 'channel'
        """
        self.cursor.execute('''
        INSERT OR REPLACE INTO whitelist VALUES (?, ?, ?, ?, ?)
        ''', (guild_id, entity_type, entity_id, added_by, time.time()))
        self.conn.commit()
    
    def remove_from_whitelist(self, guild_id, entity_type, entity_id):
        """Remove an entity from the whitelist"""
        self.cursor.execute('''
        DELETE FROM whitelist 
        WHERE guild_id = ? AND entity_type = ? AND entity_id = ?
        ''', (guild_id, entity_type, entity_id))
        self.conn.commit()
        return self.cursor.rowcount > 0  # Return True if something was deleted
    
    def get_whitelist(self, guild_id):
        """Get all whitelisted entities for a guild"""
        self.cursor.execute('''
        SELECT entity_type, entity_id FROM whitelist 
        WHERE guild_id = ?
        ''', (guild_id,))
        return self.cursor.fetchall()
    
    def is_whitelisted(self, guild_id, entity_type, entity_id):
        """Check if an entity is whitelisted"""
        self.cursor.execute('''
        SELECT 1 FROM whitelist 
        WHERE guild_id = ? AND entity_type = ? AND entity_id = ?
        ''', (guild_id, entity_type, entity_id))
        return self.cursor.fetchone() is not None
    
    def add_message(self, message):
        """Add a message to the database"""
        self.cursor.execute('''
        INSERT INTO message_history VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            message.author.id,
            message.guild.id if message.guild else 0,
            message.channel.id,
            message.id,
            message.content,
            time.time()
        ))
        self.conn.commit()
    
    def get_recent_messages(self, user_id, guild_id, seconds=60):
        """Get messages from a user in the last X seconds"""
        cutoff = time.time() - seconds
        self.cursor.execute('''
        SELECT * FROM message_history 
        WHERE user_id = ? AND guild_id = ? AND timestamp > ?
        ORDER BY timestamp DESC
        ''', (user_id, guild_id, cutoff))
        return self.cursor.fetchall()
    
    def add_warning(self, user_id, guild_id, warning_type, warned_by, expires_in=None):
        """Add a warning for a user"""
        timestamp = time.time()
        expires_at = timestamp + expires_in if expires_in else None
        
        self.cursor.execute('''
        INSERT INTO warnings VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, guild_id, warning_type, timestamp, expires_at, warned_by))
        self.conn.commit()
    
    def get_active_warnings(self, user_id, guild_id):
        """Get active warnings for a user"""
        current_time = time.time()
        self.cursor.execute('''
        SELECT * FROM warnings 
        WHERE user_id = ? AND guild_id = ? AND (expires_at IS NULL OR expires_at > ?)
        ''', (user_id, guild_id, current_time))
        return self.cursor.fetchall()
    
    def add_punishment(self, user_id, guild_id, punishment_type, reason, applied_by, duration=None):
        """Record a punishment"""
        timestamp = time.time()
        expires_at = timestamp + duration if duration else None
        
        self.cursor.execute('''
        INSERT INTO punishments VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, guild_id, punishment_type, reason, timestamp, duration, expires_at, applied_by))
        self.conn.commit()
    
    def get_punishment_history(self, user_id, guild_id):
        """Get punishment history for a user"""
        self.cursor.execute('''
        SELECT * FROM punishments 
        WHERE user_id = ? AND guild_id = ?
        ORDER BY timestamp DESC
        ''', (user_id, guild_id))
        return self.cursor.fetchall()
    
    def set_guild_config(self, guild_id, config_dict):
        """Save guild configuration"""
        import json
        config_json = json.dumps(config_dict)
        
        self.cursor.execute('''
        INSERT OR REPLACE INTO guild_config VALUES (?, ?)
        ''', (guild_id, config_json))
        self.conn.commit()
    
    def get_guild_config(self, guild_id):
        """Get guild configuration"""
        import json
        self.cursor.execute('''
        SELECT config_json FROM guild_config WHERE guild_id = ?
        ''', (guild_id,))
        result = self.cursor.fetchone()
        
        if result:
            return json.loads(result[0])
        return None
    
    def close(self):
        """Close the database connection"""
        self.conn.close()


class SpamTracker:
    def __init__(self, bot, db_path="db/security.db"):
        self.bot = bot
        self.db = SpamDatabase(db_path)
        self.message_buffer = {}  
        self.last_buffer_flush = time.time()
        self.buffer_flush_interval = 60  
        
        self.default_config = {
            'message_rate_limit': 5,  
            'time_window': 3,  
            'similar_message_threshold': 0.8,  
            'max_mentions': 4,  
            'max_repeated_messages': 3,  
            'buffer_time': 30,  
            'warning_expiry': 3600,  
            'punishments': {
                1: {'action': 'warn', 'reason': 'First spam offense'},
                2: {'action': 'mute', 'duration': 300, 'reason': 'Second spam offense'},
                3: {'action': 'kick', 'reason': 'Third spam offense'},
                4: {'action': 'ban', 'duration': 86400, 'reason': 'Fourth spam offense'}
            },
            'log_channel': None
        }
        
        self.guild_configs = {}
        bot.loop.create_task(self._periodic_buffer_flush())
    
    async def _periodic_buffer_flush(self):
        """Periodically flush message buffer to database"""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            if time.time() - self.last_buffer_flush >= self.buffer_flush_interval:
                self._flush_message_buffer()
                self.last_buffer_flush = time.time()
            await asyncio.sleep(10)
    
    def _flush_message_buffer(self):
        """Flush message buffer to database"""
        pass
    
    def get_guild_config(self, guild_id):
        """Get guild configuration with caching"""
        if guild_id not in self.guild_configs:
            config = self.db.get_guild_config(guild_id)
            if not config:
                config = self.default_config.copy()
                self.db.set_guild_config(guild_id, config)
            self.guild_configs[guild_id] = config
        return self.guild_configs[guild_id]
    
    async def process_message(self, message: nextcord.Message) -> Optional[str]:
        """
        Process a message and check for spam
        Returns: None if no spam detected, or the spam type detected
        """
        if message.author.bot or not message.guild:
            return None
            
        user_id = message.author.id
        guild_id = message.guild.id
        channel_id = message.channel.id
        
        # Check if user is whitelisted
        if self.db.is_whitelisted(guild_id, 'user', user_id):
            return None
            
        # Check if channel is whitelisted
        if self.db.is_whitelisted(guild_id, 'channel', channel_id):
            return None
            
        # Check if any of user's roles are whitelisted
        for role in message.author.roles:
            if self.db.is_whitelisted(guild_id, 'role', role.id):
                return None
        
        # Continue with existing logic
        current_time = time.time()
        
        if user_id not in self.message_buffer:
            self.message_buffer[user_id] = []
        
        self.message_buffer[user_id].append((current_time, message.content, message))
        self._clean_old_messages(user_id, current_time)
        config = self.get_guild_config(guild_id)
        
        spam_type = await self._check_spam(message, config)
        if spam_type:
            await self._handle_spam(message, spam_type, config)
            return spam_type
            
        return None
        
    def _clean_old_messages(self, user_id, current_time):
        """Remove messages older than buffer_time from memory buffer"""
        if user_id in self.message_buffer:
            buffer_time = self.default_config['buffer_time']  
            self.message_buffer[user_id] = [
                msg for msg in self.message_buffer[user_id]
                if current_time - msg[0] <= buffer_time
            ]
    
    async def _check_spam(self, message, config):
        """Check if a message is spam based on various criteria"""
        user_id = message.author.id
        recent_messages = self.message_buffer.get(user_id, [])
        time_window = config['time_window']
        rate_limit = config['message_rate_limit']
        
        current_time = time.time()
        messages_in_window = [
            msg for msg in recent_messages
            if current_time - msg[0] <= time_window
        ]
        
        if len(messages_in_window) > rate_limit:
            return "rate_limit"
        
        if len(recent_messages) >= 3:
            unique_contents = set(msg[1] for msg in recent_messages)
            if len(unique_contents) == 1 and len(recent_messages) >= config['max_repeated_messages']:
                return "repeated_messages"
        
        if len(message.mentions) > config['max_mentions']:
            return "mention_spam"
            
        return None
    
    async def _handle_spam(self, message, spam_type, config):
        """Handle detected spam according to configuration"""
        user_id = message.author.id
        guild_id = message.guild.id
        
        warnings = self.db.get_active_warnings(user_id, guild_id)
        warning_count = len(warnings)
        
        next_level = warning_count + 1
        if next_level in config['punishments']:
            punishment = config['punishments'][next_level]
            action = punishment['action']
            reason = f"{punishment['reason']} - {spam_type}"
            
            self.db.add_warning(
                user_id, 
                guild_id, 
                spam_type, 
                self.bot.user.id, 
                config['warning_expiry']
            )
            
            await self._apply_punishment(message, action, reason, punishment.get('duration'))
            await self._log_spam_incident(message, spam_type, action, reason)
    
    async def _apply_punishment(self, message, action, reason, duration=None):
        """Apply punishment to a user"""
        user = message.author
        guild = message.guild
        
        self.db.add_punishment(
            user.id,
            guild.id,
            action,
            reason,
            self.bot.user.id,
            duration
        )
        
        try:
            if action == "warn":
                embed = nextcord.Embed(
                    title="⚠️ Warning Issued",
                    description=f"{user.mention} has been warned for spam.",
                    color=nextcord.Color.orange()
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                await message.channel.send(embed=embed)
                
            elif action == "mute":
                until = datetime.datetime.utcnow() + datetime.timedelta(seconds=duration)
                await user.timeout(until, reason=reason)
                embed = nextcord.Embed(
                    title="🔇 User Muted",
                    description=f"{user.mention} has been muted for {duration} seconds.",
                    color=nextcord.Color.red()
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                await message.channel.send(embed=embed)
                
            elif action == "kick":
                await user.kick(reason=reason)
                embed = nextcord.Embed(
                    title="👢 User Kicked",
                    description=f"{user.mention} has been kicked from the server.",
                    color=nextcord.Color.dark_red()
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                await message.channel.send(embed=embed)
                
            elif action == "ban":
                if duration:
                    await guild.ban(user, reason=reason)
                    self.bot.loop.create_task(self._schedule_unban(guild.id, user.id, duration))
                    embed = nextcord.Embed(
                        title="🔨 User Banned",
                        description=f"{user.mention} has been temporarily banned for {duration} seconds.",
                        color=nextcord.Color.dark_red()
                    )
                    embed.add_field(name="Reason", value=reason, inline=False)
                    await message.channel.send(embed=embed)
                else:
                    await guild.ban(user, reason=reason, delete_message_days=1)
                    embed = nextcord.Embed(
                        title="🔨 User Banned",
                        description=f"{user.mention} has been permanently banned.",
                        color=nextcord.Color.dark_red()
                    )
                    embed.add_field(name="Reason", value=reason, inline=False)
                    await message.channel.send(embed=embed)
                    
        except nextcord.Forbidden:
            return False
        except Exception as e:
            print(f"Error applying punishment: {e}")
            return False
            
        return True
    
    async def _schedule_unban(self, guild_id, user_id, duration):
        """Schedule an unban after a duration"""
        await asyncio.sleep(duration)
        
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
                
            bans = await guild.bans()
            user_ban = next((ban for ban in bans if ban.user.id == user_id), None)
            
            if user_ban:
                await guild.unban(user_ban.user, reason="Temporary ban expired")
        except Exception as e:
            print(f"Error unbanning user: {e}")
    
    async def _log_spam_incident(self, message, spam_type, action, reason):
        """Log spam incident to the configured log channel"""
        guild = message.guild
        config = self.get_guild_config(guild.id)
        
        log_channel_id = config.get('log_channel')
        if not log_channel_id:
            return
            
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return
            
        embed = nextcord.Embed(
            title="🚨 Spam Detection",
            color=nextcord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.add_field(name="User", value=f"{message.author} ({message.author.id})", inline=False)
        embed.add_field(name="Channel", value=f"{message.channel.mention} ({message.channel.id})", inline=False)
        embed.add_field(name="Spam Type", value=spam_type, inline=True)
        embed.add_field(name="Action Taken", value=action, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Message Content", value=f"```{message.content[:1000]}```", inline=False)
        
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending log message: {e}")


class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracker = SpamTracker(bot)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Process messages for spam detection"""
        if message.author.id == self.bot.user.id or not message.guild:
            return
            
        await self.tracker.process_message(message)
    
    @commands.group(name="antispam", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def antispam(self, ctx):
        """Anti-spam configuration commands"""
        embed = nextcord.Embed(
            title="🛡️ Anti-Spam System",
            description="Use subcommands to configure anti-spam settings.",
            color=nextcord.Color.blue()
        )
        embed.add_field(
            name="Available Commands",
            value="""`config` - Show current settings
`setlog` - Set log channel
`setrate` - Set message rate limit
`setmentions` - Set mention limit
`disable` - Disable anti-spam
`enable` - Enable with defaults""",
            inline=False
        )
        await ctx.send(embed=embed)
    
    @antispam.command(name="config")
    @commands.has_permissions(manage_guild=True)
    async def show_config(self, ctx):
        """Show the current anti-spam configuration"""
        config = self.tracker.get_guild_config(ctx.guild.id)
        
        embed = nextcord.Embed(
            title="🛡️ Anti-Spam Configuration",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="Message Limits",
            value=f"**{config['message_rate_limit']}** messages per **{config['time_window']}** seconds\n"
                  f"**{config['max_mentions']}** max mentions per message\n"
                  f"**{config['max_repeated_messages']}** repeated messages within **{config['buffer_time']}** seconds",
            inline=False
        )
        
        punishment_text = ""
        for level, punishment in config['punishments'].items():
            duration = f" for {punishment.get('duration', 'N/A')} seconds" if punishment.get('duration') else ""
            punishment_text += f"**Level {level}:** {punishment['action'].capitalize()}{duration}\n"
        
        embed.add_field(name="Punishment Levels", value=punishment_text, inline=False)
        
        log_channel = ctx.guild.get_channel(config.get('log_channel', 0))
        log_channel_text = log_channel.mention if log_channel else "❌ Not set"
        embed.add_field(name="Log Channel", value=log_channel_text, inline=False)
        
        await ctx.send(embed=embed)
    
    @antispam.command(name="setlog")
    @commands.has_permissions(manage_guild=True)
    async def set_log_channel(self, ctx, channel: nextcord.TextChannel = None):
        """Set the channel for anti-spam logs"""
        if channel is None:
            channel = ctx.channel
            
        config = self.tracker.get_guild_config(ctx.guild.id)
        config['log_channel'] = channel.id
        self.tracker.db.set_guild_config(ctx.guild.id, config)
        self.tracker.guild_configs[ctx.guild.id] = config
        
        embed = nextcord.Embed(
            title="📝 Log Channel Set",
            description=f"Anti-spam logs will now be sent to {channel.mention}",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @antispam.command(name="setrate")
    @commands.has_permissions(manage_guild=True)
    async def set_rate_limit(self, ctx, messages: int, seconds: int):
        """Set the message rate limit (e.g. 5 messages in 3 seconds)"""
        if messages < 1 or seconds < 1:
            embed = nextcord.Embed(
                title="❌ Error",
                description="Values must be positive numbers",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
            
        config = self.tracker.get_guild_config(ctx.guild.id)
        config['message_rate_limit'] = messages
        config['time_window'] = seconds
        self.tracker.db.set_guild_config(ctx.guild.id, config)
        self.tracker.guild_configs[ctx.guild.id] = config
        
        embed = nextcord.Embed(
            title="✅ Rate Limit Updated",
            description=f"Set to **{messages}** messages per **{seconds}** seconds",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @antispam.command(name="setmentions")
    @commands.has_permissions(manage_guild=True)
    async def set_mention_limit(self, ctx, mentions: int):
        """Set the maximum number of mentions allowed per message"""
        if mentions < 1:
            embed = nextcord.Embed(
                title="❌ Error",
                description="Value must be a positive number",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
            
        config = self.tracker.get_guild_config(ctx.guild.id)
        config['max_mentions'] = mentions
        self.tracker.db.set_guild_config(ctx.guild.id, config)
        self.tracker.guild_configs[ctx.guild.id] = config
        
        embed = nextcord.Embed(
            title="✅ Mention Limit Updated",
            description=f"Maximum mentions per message set to **{mentions}**",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @antispam.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def disable_antispam(self, ctx):
        """Disable anti-spam features (sets very high thresholds)"""
        config = self.tracker.get_guild_config(ctx.guild.id)
        config['message_rate_limit'] = 1000
        config['max_mentions'] = 1000
        config['max_repeated_messages'] = 1000
        self.tracker.db.set_guild_config(ctx.guild.id, config)
        self.tracker.guild_configs[ctx.guild.id] = config
        
        embed = nextcord.Embed(
            title="⚠️ Anti-Spam Disabled",
            description="Anti-spam features have been effectively disabled",
            color=nextcord.Color.orange()
        )
        await ctx.send(embed=embed)
    
    @antispam.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def enable_antispam(self, ctx):
        """Enable anti-spam features with default settings"""
        config = self.tracker.default_config.copy()
        if 'log_channel' in self.tracker.get_guild_config(ctx.guild.id):
            config['log_channel'] = self.tracker.get_guild_config(ctx.guild.id)['log_channel']
            
        self.tracker.db.set_guild_config(ctx.guild.id, config)
        self.tracker.guild_configs[ctx.guild.id] = config
        
        embed = nextcord.Embed(
            title="✅ Anti-Spam Enabled",
            description="Anti-spam features have been enabled with default settings",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)


    @antispam.command()
    async def antispam_help(self, ctx):
        """Show detailed help for anti-spam commands"""
        embed = nextcord.Embed(
            title="🛡️ Anti-Spam Help",
            description="Complete command reference for the Anti-Spam system",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Configuration Commands",
            value="`antispam config` - Show current settings\n"
                  "`antispam setlog #channel` - Set log channel\n"
                  "`antispam setrate <messages> <seconds>` - Set message rate limit\n"
                  "`antispam setmentions <number>` - Set mention limit\n",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ System Commands",
            value="`antispam disable` - Disable anti-spam\n"
                  "`antispam enable` - Enable with defaults\n",
            inline=False
        )
        
        embed.add_field(
            name="📋 Whitelist Commands",
            value="`antispam whitelist` - View the whitelist\n"
                  "`antispam whitelist add @user/@role/#channel` - Add to whitelist\n"
                  "`antispam whitelist remove @user/@role/#channel` - Remove from whitelist\n",
            inline=False
        )
        
        await ctx.send(embed=embed)


    @antispam.group(name="whitelist", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def whitelist(self, ctx):
        """Manage anti-spam whitelist"""
        whitelist_entries = self.tracker.db.get_whitelist(ctx.guild.id)
        
        if not whitelist_entries:
            embed = nextcord.Embed(
                title="📋 Anti-Spam Whitelist",
                description="The whitelist is currently empty.",
                color=nextcord.Color.blue()
            )
            embed.add_field(
                name="Usage",
                value="`antispam whitelist add @user/@role/#channel` - Add to whitelist\n"
                      "`antispam whitelist remove @user/@role/#channel` - Remove from whitelist",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        embed = nextcord.Embed(
            title="📋 Anti-Spam Whitelist",
            description="The following entities are exempt from spam detection:",
            color=nextcord.Color.blue()
        )
        
        users = []
        roles = []
        channels = []
        
        for entity_type, entity_id in whitelist_entries:
            if entity_type == 'user':
                user = ctx.guild.get_member(entity_id)
                if user:
                    users.append(f"{user.mention} ({user.id})")
                else:
                    users.append(f"Unknown User ({entity_id})")
            elif entity_type == 'role':
                role = ctx.guild.get_role(entity_id)
                if role:
                    roles.append(f"{role.mention} ({role.id})")
                else:
                    roles.append(f"Unknown Role ({entity_id})")
            elif entity_type == 'channel':
                channel = ctx.guild.get_channel(entity_id)
                if channel:
                    channels.append(f"{channel.mention} ({channel.id})")
                else:
                    channels.append(f"Unknown Channel ({entity_id})")
        
        if users:
            embed.add_field(name="Whitelisted Users", value="\n".join(users), inline=False)
        if roles:
            embed.add_field(name="Whitelisted Roles", value="\n".join(roles), inline=False)
        if channels:
            embed.add_field(name="Whitelisted Channels", value="\n".join(channels), inline=False)
        
        embed.add_field(
            name="Usage",
            value="`antispam whitelist add @user/@role/#channel` - Add to whitelist\n"
                  "`antispam whitelist remove @user/@role/#channel` - Remove from whitelist",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @whitelist.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def whitelist_add(self, ctx, target: Union[nextcord.Member, nextcord.Role, nextcord.TextChannel]):
        """Add a user, role, or channel to the anti-spam whitelist"""
        guild_id = ctx.guild.id
        
        if isinstance(target, nextcord.Member):
            entity_type = 'user'
            entity_id = target.id
            name = f"{target.display_name} (User)"
        elif isinstance(target, nextcord.Role):
            entity_type = 'role'
            entity_id = target.id
            name = f"{target.name} (Role)"
        elif isinstance(target, nextcord.TextChannel):
            entity_type = 'channel'
            entity_id = target.id
            name = f"{target.name} (Channel)"
        else:
            embed = nextcord.Embed(
                title="❌ Error",
                description="Invalid target. Please mention a user, role, or channel.",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        self.tracker.db.add_to_whitelist(guild_id, entity_type, entity_id, ctx.author.id)
        
        embed = nextcord.Embed(
            title="✅ Whitelist Updated",
            description=f"Added **{name}** to the anti-spam whitelist.",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @whitelist.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def whitelist_remove(self, ctx, target: Union[nextcord.Member, nextcord.Role, nextcord.TextChannel]):
        """Remove a user, role, or channel from the anti-spam whitelist"""
        guild_id = ctx.guild.id
        
        if isinstance(target, nextcord.Member):
            entity_type = 'user'
            entity_id = target.id
            name = f"{target.display_name} (User)"
        elif isinstance(target, nextcord.Role):
            entity_type = 'role'
            entity_id = target.id
            name = f"{target.name} (Role)"
        elif isinstance(target, nextcord.TextChannel):
            entity_type = 'channel'
            entity_id = target.id
            name = f"{target.name} (Channel)"
        else:
            embed = nextcord.Embed(
                title="❌ Error",
                description="Invalid target. Please mention a user, role, or channel.",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        removed = self.tracker.db.remove_from_whitelist(guild_id, entity_type, entity_id)
        
        if removed:
            embed = nextcord.Embed(
                title="✅ Whitelist Updated",
                description=f"Removed **{name}** from the anti-spam whitelist.",
                color=nextcord.Color.green()
            )
        else:
            embed = nextcord.Embed(
                title="❌ Not Found",
                description=f"**{name}** was not in the whitelist.",
                color=nextcord.Color.orange()
            )
        
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(AntiSpam(bot))
