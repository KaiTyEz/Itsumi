import nextcord
from nextcord.ext import commands
from googletrans import Translator, LANGUAGES
from utils.katlog import logger

class TranslatorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.translator = Translator()
        self.languages = LANGUAGES

    def get_language_code(self, language_name: str) -> str:
        """Convert language name to language code"""
        language_name = language_name.lower()
        
        # Direct match
        if language_name in self.languages.values():
            for code, name in self.languages.items():
                if name == language_name:
                    return code
        
        # Partial match
        for code, name in self.languages.items():
            if language_name in name.lower():
                return code
        
        return None

    @commands.command(name="translate", aliases=["tr"])
    async def translate(self, ctx: commands.Context, target_lang: str = None):
        """
        Translate a replied message to the specified language.
        Usage: !translate [language] (when replying to a message)
        Example: !translate spanish
        """
        try:
            # Check if there's a replied message
            if not ctx.message.reference:
                await ctx.send("Please reply to a message to translate it!")
                return

            # Get the replied message
            replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if not replied_message.content:
                await ctx.send("The replied message has no content to translate!")
                return

            # If no target language specified, default to English
            if not target_lang:
                target_lang = "english"
            
            # Get language code
            lang_code = self.get_language_code(target_lang)
            if not lang_code:
                # List available languages
                languages = ", ".join(sorted(set(self.languages.values())))
                await ctx.send(f"Invalid language! Available languages:\n{languages}")
                return

            # Translate the message
            translation = self.translator.translate(replied_message.content, dest=lang_code)

            # Create embed
            embed = nextcord.Embed(
                title="Translation",
                color=nextcord.Color.blue()
            )
            
            # Add original message
            embed.add_field(
                name=f"Original ({self.languages.get(translation.src, 'Unknown')})",
                value=replied_message.content,
                inline=False
            )
            
            # Add translation
            embed.add_field(
                name=f"Translated ({self.languages.get(translation.dest, 'Unknown')})",
                value=translation.text,
                inline=False
            )
            
            # Add footer with translator info
            embed.set_footer(text=f"Translated by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
            
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in translate command: {e}")
            await ctx.send("An error occurred while translating. Please try again later.")

    @commands.command(name="languages", aliases=["langs"])
    async def list_languages(self, ctx: commands.Context):
        """List all available languages for translation"""
        try:
            # Create embed
            embed = nextcord.Embed(
                title="Available Languages",
                description="Use these language names with the translate command",
                color=nextcord.Color.blue()
            )
            
            # Add languages in chunks to avoid field length limits
            languages = sorted(set(self.languages.values()))
            chunk_size = 10
            for i in range(0, len(languages), chunk_size):
                chunk = languages[i:i + chunk_size]
                embed.add_field(
                    name=f"Languages {i+1}-{min(i+chunk_size, len(languages))}",
                    value="\n".join(chunk),
                    inline=True
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in list_languages command: {e}")
            await ctx.send("An error occurred while listing languages. Please try again later.")

def setup(bot):
    bot.add_cog(TranslatorCog(bot)) 