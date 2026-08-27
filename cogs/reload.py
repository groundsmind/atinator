import logging
from typing import TYPE_CHECKING
from common import ExtensionsFailed

from discord.ext import commands

if TYPE_CHECKING:
    from main import Bot, Context

logger = logging.getLogger(__name__)

class ReloadCog(commands.Cog):
    def __init__(self, bot: "Bot"):
        self.bot = bot

    @commands.hybrid_command(
        description="Reload all cogs",
    )
    @commands.is_owner()
    async def reload(self, ctx: "Context"):
        logger.info("%r requested reload", ctx.author.name)
        try:
            await self.bot.reload_cogs()
            await ctx.send('All cogs reloaded successfully.')
        except ExtensionsFailed as exc:
            logger.error(exc.message, exc_info=exc)
            body = '\n'.join(
                f'- {exc.name}: {exc.__cause__.__class__.__qualname__}: {exc.__cause__}' # type: ignore
                for exc in exc.exceptions
            )
            await ctx.send(
                f'Some cogs failed to reload:\n{body}\nSee the logs for the full stacktrace.'
            )

async def setup(client: "Bot"):
    await client.add_cog(ReloadCog(client))