import logging
from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from main import Bot, Context

logger = logging.getLogger(__name__)

class ReloadCog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.command()
    async def reload(self, ctx: "Context"):
        logger.info(f"{ctx.author.name} used reload command")
        await self.bot.reload_cogs()
        await ctx.message.delete()

async def setup(client: "Bot"):
    await client.add_cog(ReloadCog(client))