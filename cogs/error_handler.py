import nextcord
import sys
import traceback
from nextcord.ext import commands
from utils.katlog import logger

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command."""
        
        if hasattr(ctx.command, 'on_error'):
            return
        
        error = getattr(error, 'original', error)
        
    
        embed = nextcord.Embed(
            title="Command Error",
            color=nextcord.Color.red()
        )
        
        command_name = ctx.command.name if ctx.command else "Unknown"
        
        embed.set_footer(text=f"Command: {ctx.prefix}{command_name}")
        
        if isinstance(error, commands.CommandNotFound):
    
            embed.description = "Command not found"
            embed.add_field(name="Message", value=f"```\n{ctx.message.content}\n```", inline=False)
            embed.add_field(name="Suggestion", value="Use the help command to see available commands", inline=False)
            
        elif isinstance(error, commands.DisabledCommand):
            embed.description = f"The command `{command_name}` has been disabled."
            
        elif isinstance(error, commands.NoPrivateMessage):
            embed.description = "This command cannot be used in private messages."
            
        elif isinstance(error, commands.MissingRequiredArgument):
            
            usage = f"{ctx.prefix}{command_name}"
            for param in ctx.command.params.values():
                if param.name not in ('self', 'ctx'):
                    if param.default == param.empty:
                        usage += f" <{param.name}>"
                    else:
                        usage += f" [{param.name}]"
            
            error_message = f"```\n{usage}\n"
            param_position = usage.find(f"<{error.param.name}>")
            if param_position != -1:
                spaces = " " * param_position
                error_message += f"{spaces}^^^^\n"
            error_message += "```"
            
            embed.description = f"Missing required argument: `{error.param.name}`"
            embed.add_field(name="Correct Usage", value=error_message, inline=False)
            
        elif isinstance(error, commands.BadArgument):
            
            embed.description = "Invalid argument provided."
            embed.add_field(name="Error Details", value=str(error), inline=False)
            
            if ctx.command:
                usage = f"{ctx.prefix}{command_name}"
                for param in ctx.command.params.values():
                    if param.name not in ('self', 'ctx'):
                        if param.default == param.empty:
                            usage += f" <{param.name}>"
                        else:
                            usage += f" [{param.name}]"
                embed.add_field(name="Correct Usage", value=f"```\n{usage}\n```", inline=False)
            
        elif isinstance(error, commands.MissingPermissions):
            permissions = ', '.join([f"`{p.replace('_', ' ').title()}`" for p in error.missing_permissions])
            embed.description = "You don't have permission to use this command."
            embed.add_field(name="Missing Permissions", value=permissions, inline=False)
            
        elif isinstance(error, commands.BotMissingPermissions):
            
            permissions = ', '.join([f"`{p.replace('_', ' ').title()}`" for p in error.missing_permissions])
            embed.description = "I don't have permission to execute this command."
            embed.add_field(name="Missing Bot Permissions", value=permissions, inline=False)
            
        elif isinstance(error, commands.CommandOnCooldown):
            
            embed.description = "This command is on cooldown."
            embed.add_field(name="Try Again In", value=f"{error.retry_after:.1f} seconds", inline=False)
            
        elif isinstance(error, commands.CheckFailure):
            
            embed.description = "You do not have permission to use this command."
            
        elif isinstance(error, commands.MaxConcurrencyReached):
            
            embed.description = "This command is already being used in too many places."
            embed.add_field(name="Limit", value=f"{error.number} per {error.per.name}", inline=False)
            
        else:
            
            print(f"Ignoring exception in command {ctx.command}:", file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            
            embed.description = f"An unexpected error occurred while running this command."
            embed.add_field(name="Error Type", value=f"`{type(error).__name__}`", inline=False)
            
            if self.bot.owner_id and ctx.author.id == self.bot.owner_id:
                tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
                if len(tb) > 1000:
                    tb = tb[:1000] + "..."
                embed.add_field(name="Error Details", value=f"```py\n{tb}\n```", inline=False)
        
        try:
            await ctx.send(embed=embed)
        except nextcord.HTTPException:
            
            await ctx.send("An error occurred. Please try again later.")

def setup(bot):
    bot.add_cog(ErrorHandler(bot))
