import nextcord
from nextcord.ext import commands, tasks
import datetime
from utils.katlog import logger

class ActivityUpdater(commands.Cog):
    """A cog that updates the bot's activity to show server count."""
    
    def __init__(self, bot):
        self.bot = bot
        self.update_activity.start()
    
    def cog_unload(self):
        """Cleanup when cog is unloaded."""
        self.update_activity.cancel()
    
    @tasks.loop(hours=2)
    async def update_activity(self):
        """Update the bot's activity every 120 seconds."""
        try:
            activity = nextcord.Activity(
                type=nextcord.ActivityType.watching,
                name=f"{len(self.bot.guilds)} servers"
            )
            await self.bot.change_presence(activity=activity)
            logger.info(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Updated activity: Watching {len(self.bot.guilds)} servers")
        except Exception as e:
            logger.error(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error updating activity: {e}")
    
    @update_activity.before_loop
    async def before_update_activity(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()

def setup(bot):
    """Setup function to add the cog to the bot."""
    bot.add_cog(ActivityUpdater(bot))
