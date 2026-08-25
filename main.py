import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TOKEN")

# tester identification #
testingtxt = input("testing? [y/n]: ")
if testingtxt=="y":
    testerfile = open("testname", "r")
    testername = testerfile.read()
    testerfile.close()
    print(f"good luck {testername}")


class bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix="sone!",
            intents=intents
        )

    async def cogMgr(self, lor:str="LOAD"):
        lor = lor.upper()
        dir = "cogs"
        for root,dirs,files in os.walk(dir):
                    for file in files:
                        if file.endswith(".py") and file != "__init__.py":
                            cog_path = os.path.join(root, file).replace("\\","/").replace("/",".")[:-3]
                            if lor == "LOAD":
                                await self.load_extension(cog_path)
                                print(f"{cog_path} loaded")
                            elif lor == "RELOAD":
                                await self.reload_extension(cog_path)
                                print(f"{cog_path} reloaded")
    
    async def setup_hook(self):
        await self.cogMgr("load")
        print("all cogs loaded successfully")
        await self.tree.sync()
        

    async def on_ready(self):
        if testername:
            await bot.change_presence(activity=discord.CustomActivity(name=f"{testername} is testing"))
        print(f"{self.user.name} has connected to discord.")

bot = bot()

@bot.command()
async def reload(ctx):
    await bot.cogMgr("reload")
    await ctx.message.delete()
    print('reloaded yo')

bot.run(token=token)