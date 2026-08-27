from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import Context

from discord.ext import commands

def is_sudoer():
    async def predicate(ctx: Context) -> bool:
        return (
            await ctx.bot.is_owner(ctx.author) or
            ctx.author.id in ctx.bot.sudoers
        )

    return commands.check(predicate)

def not_none[T](obj: T | None) -> T:
    assert obj is not None
    return obj