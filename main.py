import os
import logging
import asyncio
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
    def __init__(
        self,
        *,
        tester_name: str | None,
        session: AsyncSession,
    ):
        self.tester_name = tester_name
        self.session = session

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix="sone!",
            intents=intents,
        )

    async def on_ready(self) -> None:
        user = not_none(self.user)
        logger.info("Logged in as %r", f"{user.name}#{user.discriminator}")
        if self.tester_name is not None:
            await self.change_presence(activity=discord.CustomActivity(f"{self.tester_name} is testing"))

    async def _load_cogs_impl(self, reload: bool = True) -> None:
        dir: str = "cogs"
        excs: list[commands.ExtensionFailed] = []
        for root, _dirs, files in os.walk(dir):
            for file in files:
                if not file.endswith(".py") or file == "__init__.py": continue

                cog_path = os.path.join(root, file).replace("\\", "/").replace("/", ".")[:-len(".py")]
                try:
                    if not reload or (reload and cog_path not in self.extensions):
                        await self.load_extension(cog_path)
                    else:
                        await self.reload_extension(cog_path)
                except commands.ExtensionFailed as exc:
                    excs.append(exc)

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

        await self.tree.sync()

async def main() -> None:
    discord.utils.setup_logging()

    load_dotenv()

    tester_name = os.getenv("TESTER_NAME")
    if tester_name is not None:
        logger.warning("TESTER_NAME set; launching in testing mode")

    token = not_none(os.getenv("BOKEN"))

    engine = create_async_engine("sqlite+aiosqlite:///db.sqlite")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        bot = Bot(tester_name=tester_name, session=session)
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass