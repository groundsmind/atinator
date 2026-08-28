import logging
import random
from common import not_none
from collections.abc import MutableSequence
from typing import TYPE_CHECKING, Callable, Concatenate
import datetime

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from main import Bot, Context

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import GuildData, Optout, Ping

logger = logging.getLogger(__name__)

def _choose_and_delete[T](seq: MutableSequence[T]) -> T:
    if len(seq) == 0:
        raise IndexError("Cannot choose from an empty sequence")

    index = random.randint(0, len(seq) - 1)
    value = seq[index]
    del seq[index]
    return value

def _wrap_log_guild[**P](
    log_func: Callable[P, None]
) -> Callable[Concatenate[discord.Guild, P], None]:
    def _wrapper(guild: discord.Guild, *args: P.args, **kwargs: P.kwargs):
        log_func(
            'Guild %r (ID %s): ' + args[0], # type: ignore
            guild.name, guild.id, *args[1:], # type: ignore
            **kwargs,
        )

    return _wrapper

_guild_info = _wrap_log_guild(logger.info)
_guild_warning = _wrap_log_guild(logger.warning)

class Someone(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.sm = bot.sm

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            async with self.sm() as session:
                guild_data = await session.get(GuildData, guild.id)
                if guild_data is None:
                    await self.setup_guild(session, guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        _guild_info(guild, 'Joined')
        async with self.sm() as session:
            await self.setup_guild(session, guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        _guild_info(guild, 'Removed')
        async with self.sm() as session:
            await session.delete(session.get_one(GuildData, guild.id))
            await session.commit()

    async def setup_guild(self, session: AsyncSession, guild: discord.Guild) -> None:
        role = await guild.create_role(name="someone", mentionable=True)

        session.add(GuildData(id=guild.id, role_id=role.id))
        await session.commit()

        await self.change_someone(session, guild)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        guild = message.guild
        if guild is None: return

        async with self.sm() as session:
            guild_data = await session.get(GuildData, guild.id)
            if guild_data is None:
                _guild_warning(guild, "Guild data does not exist yet")
                return

            if guild_data.role_id in message.raw_role_mentions:
                await self.change_someone(session, guild, message)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        async with self.sm() as session:
            if not await self.can_be_someone(session, member): return

            guild_data = await session.get_one(GuildData, member.guild.id)

            if member.id not in guild_data.member_bag_all:
                guild_data.member_bag_all.append(member.id)
                guild_data.member_bag.append(member.id)

            await session.commit()

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent) -> None:
        if payload.user.bot: return

        async with self.sm() as session:
            guild_data = await session.get_one(GuildData, payload.guild_id)

            try:
                guild_data.member_bag.remove(payload.user.id)
            except ValueError:
                pass

            await session.commit()

    @commands.hybrid_command(description="Opt out of being pinged with @someone in any server")
    async def optout(self, ctx: "Context") -> None:
        async with self.sm() as session:
            author_id = ctx.author.id
            opted_out = await session.get(Optout, author_id) is not None

            if opted_out:
                logger.info("User %r (ID %s) tried to opt out, but they already have", ctx.author.name, author_id)
                await ctx.send("You are already opted out! :(")
                return

            session.add(Optout(user_id=author_id))

            for guild in self.bot.guilds:
                if not guild.get_member(author_id): continue

                guild_data = await session.get_one(GuildData, guild.id)
                try:
                    guild_data.member_bag.remove(author_id)
                except ValueError:
                    pass

            await session.commit()

        logger.info("User %r (ID %s) opted out", ctx.author.name, author_id)
        await ctx.send("Goodbye! You have opted out.")

    @commands.hybrid_command(description="Opt back into being pinged with @someone")
    async def optin(self, ctx: "Context") -> None:
        async with self.sm() as session:
            author_id = ctx.author.id
            opt_out = await session.get(Optout, author_id)

            if opt_out is None:
                logger.info("User %r (ID %s) tried to opt in, but they already have", ctx.author.name, author_id)
                await ctx.send("You are already opted in! :)")
                return

            await session.delete(opt_out)

            for guild in self.bot.guilds:
                if not guild.get_member(author_id): continue

                guild_data = await session.get_one(GuildData, guild.id)
                if author_id not in guild_data.member_bag_all:
                    guild_data.member_bag_all.append(author_id)
                    guild_data.member_bag.append(author_id)

            await session.commit()

        logger.info("User %r (ID %s) opted in", ctx.author.name, author_id)
        await ctx.send("Hi! You have opted in.")

    async def change_someone(
        self,
        session: AsyncSession,
        guild: discord.Guild,
        message: discord.Message | None = None
    ) -> None:
        guild_data = await session.get_one(GuildData, guild.id)

        role_id = guild_data.role_id
        role = guild.get_role(role_id)
        if role is None:
            _guild_info(guild, "Missing role %s", role_id)
            return

        old_someone_id = guild_data.someone_id
        if old_someone_id is not None:
            if message is not None:
                self.log_ping(session, old_someone_id, message)

            old_someone_member = guild.get_member(old_someone_id)
            if old_someone_member is not None:
                await old_someone_member.remove_roles(role)

        # Instead of picking a member at random naively, we store an
        # internal "bag" of members for each guild so that the
        # distribution of people chosen to be @someone is more or less
        # fair.
        #
        # The bag is a list of member IDs, from which we randomly choose
        # and remove a value when we need a new @someone. If the bag is
        # empty, we repopulate it with all members in the server.
        #
        # `member_bag_all` stores all members that have been in the guild
        # at any point since the current bag was introduced. It is always
        # a superset of the bag.

        if len(guild_data.member_bag) == 0:
            members = [
                member.id
                async for member in guild.fetch_members()
                if await self.can_be_someone(session, member)
            ]
            guild_data.member_bag = members
            guild_data.member_bag_all = members.copy() # .copy() may not be necessary?
            _guild_info(guild, "Repopulated bag with %s members", len(members))

        member_bag_len = len(guild_data.member_bag)
        if member_bag_len == 0:
            _guild_info(guild, "No members available for @someone")
            if message is not None:
                await message.reply(
                    "But nobody came...\n"
                    "-# There are no members available for @someone. Everyone is either opted out, or a bot. (What?)",
                    mention_author=False
                )
            return

        someone_id = _choose_and_delete(guild_data.member_bag)
        guild_data.someone_id = someone_id

        await session.commit()

        member = not_none(guild.get_member(someone_id))
        _guild_info(guild, "@someone is now %r; %s left in bag", member.name, member_bag_len)
        await member.add_roles(role)

    async def can_be_someone(
        self,
        session: AsyncSession,
        member: discord.Member
    ) -> bool:
        return not member.bot and await session.get(Optout, member.id) is None

    def log_ping(
        self,
        session: AsyncSession,
        someone_id: int,
        message: discord.Message
    ) -> None:
        session.add(Ping(
            message_id=message.id,
            someone_id=someone_id,
            author_id=message.author.id,
            guild_id=not_none(message.guild).id,
            channel_id=message.channel.id,
            time=message.created_at
        ))

    @commands.hybrid_command(description="View the latest messages you were @someone'd in")
    @commands.guild_only()
    async def pings(self, ctx: "Context"):
        limit: int = 5

        async with self.sm() as session:
            result = await session.execute(
                select(Ping)
                    .filter_by(
                        someone_id=ctx.author.id,
                        guild_id=not_none(ctx.guild).id
                    )
                    .order_by(Ping.time.desc())
                    .limit(limit)
            )

            lines: list[str] = []
            for i, ping in enumerate(result.scalars()):
                lines.append(
                    f"{i + 1}. https://discord.com/channels/{ping.guild_id}/{ping.channel_id}/{ping.message_id}: "
                    f"<t:{int(ping.time.replace(tzinfo=datetime.UTC).timestamp())}:R> by <@{ping.author_id}>"
                )

            content = (
                "You haven't been @someone'd yet!"
                if len(lines) == 0 else
                "\n".join(lines) + f"\n-# Showing {limit} latest pings"
            )
            await ctx.send(
                content,
                allowed_mentions=discord.AllowedMentions(users=False),
                ephemeral=True,
            )

    @commands.hybrid_command(description="View the bot's info for this guild")
    @commands.guild_only()
    async def guildinfo(self, ctx: "Context"):
        guild_id = not_none(ctx.guild).id

        async with self.sm() as session:
            ping_count = not_none((
                await session.execute(
                    select(func.count())
                        .select_from(Ping)
                        .filter_by(guild_id=guild_id)
                )
            ).scalar())

            last_pinged_member_id = not_none((
                await session.execute(
                    select(Ping.someone_id)
                        .select_from(Ping)
                        .filter_by(guild_id=guild_id)
                        .order_by(Ping.time.desc())
                        .limit(1)
                )
            ).scalar())

            guild_data = await session.get_one(GuildData, guild_id)

            await ctx.send(
                embed=discord.Embed()
                    .add_field(name="Last pinged member", value=f"<@{last_pinged_member_id}>", inline=False)
                    .add_field(name="Current member bag length", value=len(guild_data.member_bag), inline=False)
                    .add_field(name="Total ping count", value=ping_count, inline=False),
                allowed_mentions=discord.AllowedMentions(users=False),
            )

async def setup(client: "Bot"):
    await client.add_cog(Someone(client))