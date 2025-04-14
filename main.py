import nextcord
from nextcord.ext import commands
from utils.katlog import logger
from utils.config import Config
import os


class LazyBot:

    def __init__(self):
        os.makedirs("db", exist_ok=True)
        os.makedirs("./cogs", exist_ok=True)

        self.bot = commands.Bot(
            intents=nextcord.Intents.all(),
            help_command=None,
            command_prefix="i.",
            owner_id="1118160684119752834",
        )

        self._setup_events()
        self.loaded_cogs = 0
        self._load_cogs()

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f"Loaded {self.loaded_cogs} cogs")
            logger.success(f"{self.bot.user} is now online! ✅")

CA        """Load all cog files from the cogs directory"""
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and not filename.startswith("_"):
                try:
                    self.bot.load_extension(f"cogs.{filename[:-3]}")
                    self.loaded_cogs += 1
                    logger.info(f"Loaded cog: {filename[:-3]}")
                except Exception as e:
                    logger.error(f"Failed to load cog {filename[:-3]}: {e}")

    def run(self):
        """Run the bot with the token from config"""
        self.bot.run(Config.token)


def main():
    lazy_bot = LazyBot()
    lazy_bot.run()


if __name__ == "__main__":
    main()
