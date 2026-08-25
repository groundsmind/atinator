import discord
from discord.ext import commands
from discord import app_commands
import random


class randmember(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.members = []

    async def get_all_members(self, ctx):
        #gets all non-bot members
        self.members = [member async for member in ctx.guild.fetch_members(limit=None) if not member.bot]
        random.shuffle(self.members)
        print("members:")
        print(self.members)

    async def first_set(self, ctx):
        await self.members[0].add_roles(self.role)
        print(f"{self.members[0].name} is now @someone!")

    async def change_someone(self, ctx):
        if len(self.members) > 1:
            await self.members[0].remove_roles(self.role)
            self.members.pop(0)
            await self.members[0].add_roles(self.role)
            print(f"{self.members[0].name} is now @someone!")
        else:
            await self.get_all_members(ctx)
            await self.first_set(ctx)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def setup(self, ctx):
        # makes someone role if it doesnt exist
        self.role = discord.utils.get(ctx.guild.roles, name="someone")
        if not self.role:
            new_role = await ctx.guild.create_role(
                name="someone",
                mentionable=True
            )
            self.role = new_role
            print('server didn\'t have "someone", role created!')
        else:
            print('server already has "someone" role.')

        # fetch all members
        await self.get_all_members(ctx)
        # pick someone to be it
        await self.first_set(ctx)

        await ctx.message.delete()
    
    @commands.Cog.listener()
    async def on_message(self, ctx):
        # ignores self messages
        if ctx.author == self.bot.user:
            return

        if str(self.role.id) in ctx.content and self.role:
            await self.change_someone(ctx)


async def setup(client):
    await client.add_cog(randmember(client))