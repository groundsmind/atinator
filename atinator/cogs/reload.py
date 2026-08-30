import logging
from common import ExtensionsFailed

from discord.ext import commands

from bot import Bot, Context

logger = logging.getLogger(__name__)

class Reload(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.hybrid_command(description="Reload all cogs")
    @commands.is_owner()
    async def reload(self, ctx: Context):
        logger.info("User %r (ID %s) requested reload", ctx.author.name, ctx.author.id)
        try:
            await self.bot.reload_cogs()
            await ctx.send('All cogs reloaded successfully.')
        except ExtensionsFailed as exc:
            logger.error(exc.message, exc_info=exc)
            body = '\n'.join(
                f"- {exc.name}: " # type: ignore
                f"{exc.__cause__.__class__.__qualname__}: {exc.__cause__}"
                for exc in exc.exceptions
            )
            await ctx.send(
                f"Some cogs failed to reload:\n"
                f"{body}"
                f"See the logs for the full stacktrace."
            )

async def setup(client: "Bot"):
    await client.add_cog(Reload(client))