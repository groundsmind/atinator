from dataclasses import dataclass, field
import logging
import asyncio
from collections.abc import Callable, Awaitable
from common import not_none, ExtensionsFailed

from dotenv import load_dotenv

from config import ConfigBase

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

_cogs = [
    "cogs.someone",
    "cogs.reload",
]

@dataclass
class Config(ConfigBase):
    token: str
    db_url: str = "sqlite+aiosqlite:///db.sqlite"
    command_prefixes: set[str] = field(default_factory=lambda: {"sone!", "at!"})
    use_jishaku: bool = True

class Bot(commands.Bot):
    def __init__(self, config: Config, sm: Callable[[], AsyncSession]):
        self.sm = sm
        self.config = config

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix=config.command_prefixes,
            intents=intents,
        )

    async def on_ready(self) -> None:
        user = not_none(self.user)
        logger.info("Logged in as %r", f"{user.name}#{user.discriminator}")

    async def _load_cogs_impl(self, reload: bool = True) -> None:
        async def load(name: str):
            try:
                if not reload or (reload and name not in self.extensions):
                    await self.load_extension(name)
                else:
                    await self.reload_extension(name)
            except commands.ExtensionFailed as exc:
                return exc

        coros: list[Awaitable[commands.ExtensionFailed | None]] = []
        if self.config.use_jishaku:
            coros.append(load("jishaku"))
        for name in _cogs:
            coros.append(load(name))
        excs = [exc for exc in await asyncio.gather(*coros) if exc is not None]

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

    load_dotenv()

    config = Config.from_env()

    engine = create_async_engine(config.db_url)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    bot = Bot(config, sm)
    await bot.start(config.token)