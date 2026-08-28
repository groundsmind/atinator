import os
import logging
import re
from typing import Callable, Iterable, cast
from common import not_none, ExtensionsFailed

from dotenv import load_dotenv

import discord
from discord.ext import commands

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from models import Base

type Context = commands.Context[Bot]

logger = logging.getLogger(__name__)

class Bot(commands.Bot):
    def __init__(self, *, command_prefixes: Iterable[str], sm: Callable[[], AsyncSession]):
        self.sm = sm

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix=command_prefixes,
            intents=intents,
        )

    async def on_ready(self) -> None:
        user = not_none(self.user)
        logger.info("Logged in as %r", f"{user.name}#{user.discriminator}")

    async def _load_cogs_impl(self, reload: bool = True) -> None:
        dir: str = "cogs"
        names: list[str] = ["jishaku"]
        for dir_path, _, filenames in os.walk(dir):
            for filename in filenames:
                if not filename.endswith(".py"): continue
                names.append(os.path.join(dir_path, filename.removesuffix(".py")).replace("/", "."))

        excs: list[commands.ExtensionFailed] = []
        for name in names:
            try:
                if not reload or (reload and name not in self.extensions):
                    await self.load_extension(name)
                else:
                    await self.reload_extension(name)
            except commands.ExtensionFailed as exc:
                excs.append(exc)

        await self.tree.sync()

        if len(excs) == 0:
            logger.info("All cogs loaded successfully")
        else:
            raise ExtensionsFailed("One or more cogs failed to load", excs)

    async def load_cogs(self) -> None:
        await self._load_cogs_impl(reload=False)

    async def reload_cogs(self) -> None:
        await self._load_cogs_impl(reload=True)
    
    async def setup_hook(self) -> None:
        try:
            await self.load_cogs()
        except ExtensionsFailed as exc:
            logger.error(exc.message, exc_info=exc)

async def main() -> None:
    discord.utils.setup_logging()

    # TODO: put env parsing somewhere else if/when we have more config options 
    load_dotenv()

    token = not_none(os.getenv("TOKEN"))

    command_prefixes_raw = os.getenv("COMMAND_PREFIXES")
    command_prefixes = (
        ["at!"]
        if command_prefixes_raw is None else
        [
            cast(str, p).replace("\\,", ",")
            for p in re.split(r"(?<!\\),", command_prefixes_raw)
        ]
    )

    engine = create_async_engine(os.getenv("DB_URL", "sqlite+aiosqlite:///db.sqlite"))
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    bot = Bot(command_prefixes=command_prefixes, sm=sm)
    await bot.start(token)