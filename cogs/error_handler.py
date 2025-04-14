import nextcord
from nextcord.ext import commands
from utils.katlog import logger
import traceback
import sys
import datetime

class ErrorHandler(commands.Cog):
    """Handles errors for all commands"""

    def __init__(self, bot):
        self.bot = bot
        self.error_webhook_url = "YOUR_WEBHOOK_URL"  # Replace with your webhook URL

    async def send_error_webhook(self, error, ctx):
        """Send error details to webhook"""
        try:
            webhook = nextcord.Webhook.from_url(self.error_webhook_url, adapter=nextcord.AsyncWebhookAdapter(self.bot))
            
            # Create a detailed error embed
            embed = nextcord.Embed(
                title="🚨 Command Error",
                color=0xFF0000,
                timestamp=datetime.datetime.now()
            )
            
            # Add command information
            embed.add_field(
                name="Command",
                value=f"```{ctx.command}```",
                inline=False
            )
            
            # Add error information
            embed.add_field(
                name="Error Type",
                value=f"```{type(error).__name__}```",
                inline=True
            )
            
            embed.add_field(
                name="Error Message",
                value=f"```{str(error)}```",
                inline=True
            )
            
            # Add context information
            embed.add_field(
                name="Channel",
                value=f"<#{ctx.channel.id}> ({ctx.channel.name})",
                inline=True
            )
            
            embed.add_field(
                name="User",
                value=f"<@{ctx.author.id}> ({ctx.author.name}#{ctx.author.discriminator})",
                inline=True
            )
            
            embed.add_field(
                name="Guild",
                value=f"{ctx.guild.name} ({ctx.guild.id})",
                inline=True
            )
            
            # Add message content
            if ctx.message.content:
                embed.add_field(
                    name="Message Content",
                    value=f"```{ctx.message.content[:1000]}```",
                    inline=False
                )
            
            # Add traceback
            tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
            if len(tb) > 1000:
                tb = tb[:997] + "..."
            embed.add_field(
                name="Traceback",
                value=f"```py\n{tb}```",
                inline=False
            )
            
            await webhook.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send error webhook: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        try:
            # Log the error
            logger.error(f"Command error in {ctx.command}: {error}")
            
            # Send error to webhook
            await self.send_error_webhook(error, ctx)
            
            # Create error embed
            embed = nextcord.Embed(
                title="❌ Error",
                color=0xFF0000,
                timestamp=datetime.datetime.now()
            )
            
            # Handle different types of errors
            if isinstance(error, commands.MissingPermissions):
                embed.description = "You don't have permission to use this command."
                embed.add_field(
                    name="Required Permissions",
                    value="\n".join(f"• {perm.replace('_', ' ').title()}" for perm in error.missing_permissions),
                    inline=False
                )
            
            elif isinstance(error, commands.BotMissingPermissions):
                embed.description = "I don't have the required permissions to do that."
                embed.add_field(
                    name="Missing Permissions",
                    value="\n".join(f"• {perm.replace('_', ' ').title()}" for perm in error.missing_permissions),
                    inline=False
                )
            
            elif isinstance(error, commands.MissingRequiredArgument):
                embed.description = f"Missing required argument: `{error.param.name}`"
                if ctx.command.help:
                    embed.add_field(
                        name="Usage",
                        value=f"```{ctx.prefix}{ctx.command.name} {ctx.command.signature}```",
                        inline=False
                    )
                    embed.add_field(
                        name="Help",
                        value=ctx.command.help,
                        inline=False
                    )
            
            elif isinstance(error, commands.BadArgument):
                embed.description = "Invalid argument provided."
                if ctx.command.help:
                    embed.add_field(
                        name="Usage",
                        value=f"```{ctx.prefix}{ctx.command.name} {ctx.command.signature}```",
                        inline=False
                    )
                    embed.add_field(
                        name="Help",
                        value=ctx.command.help,
                        inline=False
                    )
            
            elif isinstance(error, commands.CommandOnCooldown):
                embed.description = "This command is on cooldown."
                embed.add_field(
                    name="Time Remaining",
                    value=f"Try again in {error.retry_after:.1f} seconds",
                    inline=False
                )
            
            elif isinstance(error, commands.NoPrivateMessage):
                embed.description = "This command cannot be used in private messages."
            
            elif isinstance(error, commands.CheckFailure):
                embed.description = "You don't meet the requirements to use this command."
            
            else:
                # For unexpected errors
                embed.description = "An unexpected error occurred."
                embed.add_field(
                    name="Error Details",
                    value=f"```{str(error)[:1000]}```",
                    inline=False
                )
            
            # Add footer with error ID
            error_id = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            embed.set_footer(text=f"Error ID: {error_id}")
            
            # Send the error message
            await ctx.send(embed=embed)
            
        except Exception as e:
            # If error handling fails, log it
            logger.critical(f"Error in error handler: {e}")
            logger.critical(traceback.format_exc())
            
            # Try to send a basic error message
            try:
                await ctx.send("❌ An error occurred while processing your command. Please try again later.")
            except:
                pass

def setup(bot):
    bot.add_cog(ErrorHandler(bot))
