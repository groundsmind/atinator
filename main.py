import os
import logging
import asyncio
from common import not_none

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
        load_func = self.reload_extension if reload else self.load_extension

        dir: str = "cogs"
        for root, _dirs, files in os.walk(dir):
            for file in files:
                if not file.endswith(".py") or file == "__init__.py": continue

                cog_path = os.path.join(root, file).replace("\\", "/").replace("/", ".")[:-len(".py")]
                try:
                    await load_func(cog_path)
                    logger.info("Loaded cog %r", cog_path)
                except Exception as exc:
                    logger.error("Cog %r raised an error", cog_path, exc_info=exc)

    async def load_cogs(self) -> None:
        await self._load_cogs_impl(reload=False)

    async def reload_cogs(self) -> None:
        await self._load_cogs_impl(reload=True)
    
    async def setup_hook(self) -> None:
        await self.load_cogs()
        await self.tree.sync()

async def main() -> None:
    discord.utils.setup_logging()

    load_dotenv()

    tester_name = os.getenv("TESTER_NAME")
    if tester_name is not None:
        logger.warning("TESTER_NAME set; launching in testing mode")

    token = not_none(os.getenv("TOKEN"))

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