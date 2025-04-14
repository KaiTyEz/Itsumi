import nextcord
from nextcord.ext import commands
import aiosqlite
import datetime
import pytimeparse
import os
from utils.katlog import logger


class Moderation(commands.Cog):
    """Moderation commands for server management"""

    def __init__(self, bot):
        self.bot = bot
        self.db_path = "db/moderation.db"
        bot.loop.create_task(self.init_db())

    async def init_db(self):
        """Initialize the database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Create cases table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    guild_id INTEGER NOT NULL,
                    duration TEXT
                )
            """
            )

            # Create mod log channels table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS mod_log_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL
                )
            """
            )

            await db.commit()

    async def create_case(
        self, guild_id, user_id, moderator_id, action, reason=None, duration=None
    ):
        """Create a new moderation case and return the case ID"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO cases 
                   (user_id, moderator_id, action, reason, guild_id, duration) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, moderator_id, action, reason, guild_id, duration),
            )
            await db.commit()
            case_id = cursor.lastrowid
            return case_id

    async def get_case(self, case_id):
        """Get case details by case ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM cases WHERE case_id = ?", (case_id,)
            ) as cursor:
                case = await cursor.fetchone()
                if case:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, case))
                return None

    async def get_user_cases(self, guild_id, user_id):
        """Get all cases for a specific user in a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM cases WHERE guild_id = ? AND user_id = ? ORDER BY case_id DESC",
                (guild_id, user_id),
            ) as cursor:
                cases = await cursor.fetchall()
                if cases:
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, case)) for case in cases]
                return []

    def create_mod_embed(
        self, title, description, user, moderator, case_id, color=0xE74C3C, **kwargs
    ):
        """Create a formatted embed for moderation actions"""
        embed = nextcord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.now(),
        )

        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="User", value=f"{user.mention} ({user.name}) {user.id}", inline=True)
        embed.add_field(
            name="Moderator",
            value=f"{moderator.mention} ({moderator.name}) {moderator.id}",
            inline=True,
        )

        for key, value in kwargs.items():
            if value:
                embed.add_field(
                    name=key.replace("_", " ").title(), value=value, inline=False
                )

        embed.set_footer(text=f"Case ID: {case_id}")
        return embed

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: nextcord.Member, *, reason=None):
        """Kick a member from the server"""
        if (
            member.top_role.position >= ctx.author.top_role.position
            and ctx.author.id != ctx.guild.owner_id
        ):
            return await ctx.send("You can't kick someone with a higher or equal role.")

        # Create case in database
        case_id = await self.create_case(
            ctx.guild.id, member.id, ctx.author.id, "kick", reason
        )

        # Create embed for response
        embed = self.create_mod_embed(
            "Member Kicked",
            f"{member.mention} has been kicked from the server.",
            member,
            ctx.author,
            case_id,
            reason=reason,
        )

        # DM the kicked user if possible
        try:
            user_embed = nextcord.Embed(
                title=f"You've been kicked from {ctx.guild.name}",
                description=f"Reason: {reason or 'No reason provided'}",
                color=0xE74C3C,
            )
            await member.send(embed=user_embed)
        except:
            pass

        # Kick the member
        await member.kick(reason=f"[{ctx.author}] {reason or 'No reason provided'}")

        # Send mod log
        await self.send_mod_log(ctx.guild, embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(
        self, ctx, member: nextcord.Member, delete_days: int = 0, *, reason=None
    ):
        """Ban a member from the server

        Usage: i.ban @user [delete_days] [reason]
        delete_days: Number of days of message history to delete (0-7)
        """
        if (
            member.top_role.position >= ctx.author.top_role.position
            and ctx.author.id != ctx.guild.owner_id
        ):
            return await ctx.send("You can't ban someone with a higher or equal role.")

        # Validate delete_days
        if not 0 <= delete_days <= 7:
            return await ctx.send("Delete days must be between 0 and 7.")

        # Create case in database
        case_id = await self.create_case(
            ctx.guild.id, member.id, ctx.author.id, "ban", reason
        )

        # Create embed for response
        embed = self.create_mod_embed(
            "Member Banned",
            f"{member.mention} has been banned from the server.",
            member,
            ctx.author,
            case_id,
            reason=reason,
            delete_messages=f"{delete_days} days" if delete_days else "None",
        )

        # DM the banned user if possible
        try:
            user_embed = nextcord.Embed(
                title=f"You've been banned from {ctx.guild.name}",
                description=f"Reason: {reason or 'No reason provided'}",
                color=0xE74C3C,
            )
            await member.send(embed=user_embed)
        except:
            pass

        # Ban the member
        await member.ban(
            reason=f"[{ctx.author}] {reason or 'No reason provided'}",
        )

        # Send mod log
        await self.send_mod_log(ctx.guild, embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(
        self, ctx, member: nextcord.Member, duration: str, *, reason=None
    ):
        """Timeout a member (prevent them from sending messages)

        Usage: i.timeout @user 1h30m [reason]
        Duration formats: 30m, 1h30m, 1d12h, 30s, etc.
        """
        if (
            member.top_role.position >= ctx.author.top_role.position
            and ctx.author.id != ctx.guild.owner_id
        ):
            return await ctx.send(
                "You can't timeout someone with a higher or equal role."
            )

        # Parse the duration
        seconds = pytimeparse.parse(duration)
        if not seconds:
            return await ctx.send(
                "Invalid duration format. Use formats like '1h30m', '1d12h', etc."
            )

        if seconds > 2419200:  # Discord max timeout is 28 days
            return await ctx.send("Timeout duration cannot exceed 28 days.")

        # Calculate end time
        until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            seconds=seconds
        )

        # Create human-readable duration string
        duration_str = self.format_duration(seconds)

        # Create case in database
        case_id = await self.create_case(
            ctx.guild.id, member.id, ctx.author.id, "timeout", reason, duration_str
        )

        # Create embed for response
        embed = self.create_mod_embed(
            "Member Timed Out",
            f"{member.mention} has been timed out.",
            member,
            ctx.author,
            case_id,
            reason=reason,
            duration=duration_str,
            expires=f"<t:{int(until.timestamp())}:R>",
        )

        # DM the user if possible
        try:
            user_embed = nextcord.Embed(
                title=f"You've been timed out in {ctx.guild.name}",
                description=f"Duration: {duration_str}\nReason: {reason or 'No reason provided'}\nExpires: <t:{int(until.timestamp())}:R>",
                color=0xE74C3C,
            )
            await member.send(embed=user_embed)
        except:
            pass

        # Apply timeout
        await member.timeout(
            until, reason=f"[{ctx.author}] {reason or 'No reason provided'}"
        )

        # Send mod log
        await self.send_mod_log(ctx.guild, embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: nextcord.Member, *, reason):
        """Warn a member (creates a moderation record)

        Usage: i.warn @user Reason for warning
        """
        if (
            member.top_role.position >= ctx.author.top_role.position
            and ctx.author.id != ctx.guild.owner_id
        ):
            return await ctx.send("You can't warn someone with a higher or equal role.")

        # Create case in database
        case_id = await self.create_case(
            ctx.guild.id, member.id, ctx.author.id, "warn", reason
        )

        # Create embed for response
        embed = self.create_mod_embed(
            "Member Warned",
            f"{member.mention} has been warned.",
            member,
            ctx.author,
            case_id,
            reason=reason,
            color=0xF39C12,  # Orange for warnings
        )

        # DM the warned user if possible
        try:
            user_embed = nextcord.Embed(
                title=f"You've been warned in {ctx.guild.name}",
                description=f"Reason: {reason}",
                color=0xF39C12,
            )
            await member.send(embed=user_embed)
        except:
            pass

        # Send mod log
        await self.send_mod_log(ctx.guild, embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def case(self, ctx, case_id: int = None, user: nextcord.Member = None):
        """Look up a moderation case by ID or view a user's cases

        Usage:
        i.case 123 - Look up case #123
        i.case @user - View cases for a user
        """
        if case_id is None and user is None:
            # Check if we can interpret the command as "case @user"
            if len(ctx.message.mentions) > 0:
                user = ctx.message.mentions[0]
            else:
                return await ctx.send(
                    "Please provide either a case ID or a user to look up cases for."
                )

        if case_id:
            # Look up specific case
            case = await self.get_case(case_id)
            if not case or case["guild_id"] != ctx.guild.id:
                return await ctx.send(f"Case #{case_id} not found.")

            try:
                case_user = await self.bot.fetch_user(case["user_id"])
                case_mod = await self.bot.fetch_user(case["moderator_id"])
            except:
                case_user = f"Unknown User ({case['user_id']})"
                case_mod = f"Unknown User ({case['moderator_id']})"

            embed = nextcord.Embed(
                title=f"Case #{case['case_id']} - {case['action'].title()}",
                color=self.get_action_color(case["action"]),
                timestamp=datetime.datetime.fromisoformat(case["timestamp"]),
            )

            embed.add_field(
                name="User",
                value=f"<@{case['user_id']}>\n{getattr(case_user, 'name', case_user)}",
                inline=True,
            )
            embed.add_field(
                name="Moderator",
                value=f"<@{case['moderator_id']}>\n{getattr(case_mod, 'name', case_mod)}",
                inline=True,
            )

            if case["reason"]:
                embed.add_field(name="Reason", value=case["reason"], inline=False)

            if case["duration"]:
                embed.add_field(name="Duration", value=case["duration"], inline=False)

            await ctx.send(embed=embed)

        else:
            # Look up user's cases
            cases = await self.get_user_cases(ctx.guild.id, user.id)
            if not cases:
                return await ctx.send(f"No cases found for {user.mention}.")

            embed = nextcord.Embed(
                title=f"Moderation History for {user.name}",
                description=f"Total cases: {len(cases)}",
                color=0x3498DB,
                timestamp=datetime.datetime.now(),
            )

            embed.set_thumbnail(url=user.display_avatar.url)

            # Add the 5 most recent cases
            for i, case in enumerate(cases[:5]):
                case_time = datetime.datetime.fromisoformat(case["timestamp"])
                value = f"**Moderator:** <@{case['moderator_id']}>\n"
                value += f"**Date:** <t:{int(case_time.timestamp())}:R>\n"
                if case["reason"]:
                    value += f"**Reason:** {case['reason']}\n"
                if case["duration"]:
                    value += f"**Duration:** {case['duration']}"

                embed.add_field(
                    name=f"#{case['case_id']} - {case['action'].title()}",
                    value=value.strip(),
                    inline=False,
                )

            if len(cases) > 5:
                embed.set_footer(
                    text=f"Showing 5 most recent cases out of {len(cases)}. Use i.case with a specific case ID for details."
                )

            await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def modlog(self, ctx, channel: nextcord.TextChannel = None):
        """Configure the moderation log channel

        Usage:
        i.modlog #channel - Set the mod log channel
        i.modlog - Show current mod log channel
        """
        async with aiosqlite.connect(self.db_path) as db:
            if channel is None:
                # Show current setting
                async with db.execute(
                    "SELECT channel_id FROM mod_log_channels WHERE guild_id = ?",
                    (ctx.guild.id,),
                ) as cursor:
                    result = await cursor.fetchone()
                    if result:
                        channel_id = result[0]
                        return await ctx.send(
                            f"Current modlog channel: <#{channel_id}>"
                        )
                    else:
                        return await ctx.send("No modlog channel configured.")
            else:
                # Upsert the channel
                await db.execute(
                    """
                    INSERT INTO mod_log_channels (guild_id, channel_id) 
                    VALUES (?, ?) 
                    ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?
                """,
                    (ctx.guild.id, channel.id, channel.id),
                )
                await db.commit()

                await ctx.send(f"Modlog channel set to {channel.mention}")

    async def send_mod_log(self, guild, embed):
        """Send a moderation action to the configured mod log channel"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT channel_id FROM mod_log_channels WHERE guild_id = ?",
                (guild.id,),
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    channel_id = result[0]
                    channel = guild.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.send(embed=embed)
                        except Exception as e:
                            logger.error(f"Failed to send mod log: {e}")

    def format_duration(self, seconds):
        """Format seconds into a human-readable duration string"""
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")

        return " ".join(parts)

    def get_action_color(self, action):
        """Get the appropriate color for each action type"""
        colors = {
            "warn": 0xF39C12,  # Orange
            "timeout": 0xF1C40F,  # Yellow
            "kick": 0xE67E22,  # Dark Orange
            "ban": 0xE74C3C,  # Red
            "unban": 0x2ECC71,  # Green
        }
        return colors.get(action.lower(), 0x3498DB)  # Default blue


def setup(bot):
    bot.add_cog(Moderation(bot))
