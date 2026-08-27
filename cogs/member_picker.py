import logging
import random
from common import not_none
from collections.abc import MutableSequence
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from main import Bot, Context

from models import GuildData, OptOut

logger = logging.getLogger(__name__)

def _choose_and_delete[T](seq: MutableSequence[T]) -> T:
    if len(seq) == 0:
        raise IndexError("Cannot choose from an empty sequence")

    index = random.randint(0, len(seq) - 1)
    value = seq[index]
    del seq[index]
    return value

class MemberPickerCog(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.session = bot.session

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            async with self.session.begin():
                guild_data = await self.session.get(GuildData, guild.id)

            if guild_data is None:
                await self.setup_guild(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.setup_guild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        async with self.session.begin():
            await self.session.delete(self.session.get_one(GuildData, guild.id))
            await self.session.commit()

    async def setup_guild(self, guild: discord.Guild) -> None:
        role = await guild.create_role(name="someone", mentionable=True)
        async with self.session.begin():
            self.session.add(GuildData(id=guild.id, role_id=role.id))
            await self.session.commit()

        await self.change_someone(guild)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        guild = message.guild
        if guild is None: return

        async with self.session.begin():
            guild_data = await self.session.get_one(GuildData, guild.id)

        if guild_data.role_id in message.raw_role_mentions:
            await self.change_someone(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if not await self.can_be_someone(member=member): return

        async with self.session.begin():
            guild_data = await self.session.get_one(GuildData, member.guild.id)

            if member.id not in guild_data.member_bag_all:
                guild_data.member_bag_all.append(member.id)
                guild_data.member_bag.append(member.id)

            await self.session.commit()

    @commands.Cog.listener()
    async def on_raw_member_remove(self, payload: discord.RawMemberRemoveEvent) -> None:
        if payload.user.bot: return

        async with self.session.begin():
            guild_data = await self.session.get_one(GuildData, payload.guild_id)

            try:
                guild_data.member_bag.remove(payload.user.id)
            except ValueError:
                pass

            await self.session.commit()

    @commands.hybrid_command(name="optout", description="Makes it so you're not pingable by @someone.")
    async def optout(self, ctx: "Context") -> None:
        async with self.session.begin():
            author_id = ctx.author.id
            guild_data = await self.session.get_one(GuildData, not_none(ctx.guild).id)
            opted_out = await self.session.get(OptOut, author_id)
            if opted_out is None:
                self.session.add(OptOut(id=author_id))
                if author_id not in guild_data.member_bag_all:
                    guild_data.member_bag_all.pop(author_id)
                    guild_data.member_bag.pop(author_id)

                    logger.info(f"{ctx.author.name} opted out.")
                    await ctx.send(f'Goodbye! you have opted out.')
            else:
                logger.info(f"{ctx.author.name} tried opting out, but they have already.")
                await ctx.send(f'You are already opted out! :(')

            await self.session.commit()

    @commands.hybrid_command(name="optin", description="Adds you back to the pingable @someone list.")
    async def optin(self, ctx: "Context") -> None:
        async with self.session.begin():
            author_id = ctx.author.id
            guild_data = await self.session.get_one(GuildData, not_none(ctx.guild).id)
            opted_out = await self.session.get(OptOut, author_id)
            if opted_out is not None:
                await self.session.delete(OptOut(id=author_id))
                if author_id not in guild_data.member_bag_all:
                    guild_data.member_bag_all.append(author_id)
                    guild_data.member_bag.append(author_id)

                    logger.info(f"{ctx.author.name} opted back in.")
                    await ctx.send(f'Hi you have opted back in.')
            else:
                logger.info(f"{ctx.author.name} tried opting in, but they have already.")
                await ctx.send(f'You are already opted in! :)')

            await self.session.commit()



    async def change_someone(self, guild: discord.Guild):
        async with self.session.begin():
            guild_data = await self.session.get_one(GuildData, guild.id)

            role_id = guild_data.role_id
            role = guild.get_role(role_id)
            if role is None:
                logger.error("Guild %r: Missing role %s", guild.name, role_id)
                return

            old_someone_id = guild_data.someone_id
            if old_someone_id is not None:
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
                    if await self.can_be_someone(member=member)
                ]
                guild_data.member_bag = members
                guild_data.member_bag_all = members.copy() # .copy() may not be necessary?
                logger.info('Guild %r: Repopulated bag with %s members', guild.name, len(members))

            someone_id = _choose_and_delete(guild_data.member_bag)
            guild_data.someone_id = someone_id

            member_bag_len = len(guild_data.member_bag)

            await self.session.commit()

        member = not_none(guild.get_member(someone_id))
        logger.info("Guild %r: @someone is now %r; %s left in bag", guild.name, member.name, member_bag_len)
        await member.add_roles(role)

    async def can_be_someone(self, member: discord.Member):
        async with self.session.begin():
            if not member.bot and await self.session.get(OptOut, member.id) is None:
                return True
            return False

async def setup(client: "Bot"):
    await client.add_cog(MemberPickerCog(client))