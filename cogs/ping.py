import nextcord
from nextcord.ext import commands
import datetime


class PingCog(commands.Cog):
    """A simple ping command cog"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping")
    async def _ping(self, ctx):
        """Check the bot's latency to Discord"""

        latency = round(self.bot.latency * 1000)

        now = datetime.datetime.now(datetime.timezone.utc)
        embed = nextcord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: `{latency}ms`",
            color=nextcord.Color.green(),
            timestamp=now,
        )

        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        embed.set_author(
            name=self.bot.user.display_name, icon_url=self.bot.user.display_avatar.url
        )

        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(PingCog(bot))
