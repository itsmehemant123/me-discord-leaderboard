import discord
import json
import logging
import inspect
from discord.ext import commands
from leaderboard import LeaderBoyt

logging.basicConfig(level=logging.INFO)

with open('./config/auth.json') as data_file:
    auth = json.load(data_file)

bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'), description='Leaderboyt, yay!', max_messages=5000)
boyt = LeaderBoyt(bot)
bot.add_cog(boyt)

@bot.event
async def on_ready():
    logging.info('Logged in as:{0} (ID: {0.id})'.format(bot.user))

@bot.event
async def on_message(message):
    if (message.author.id != bot.user.id):
        if (message.content.startswith('!')):
            await bot.process_commands(message)
        else:
            print('shut', message)
            await boyt.readmeme(message)

@bot.event
async def on_reaction_add(reaction, user):
    await boyt.add_reaction(reaction, user)

@bot.event
async def on_reaction_remove(reaction, user):
    await boyt.remove_reaction(reaction, user)

@bot.event
async def on_reaction_clear(message, reactions):
    await boyt.clear_reaction(message, reactions)

bot.run(auth['token'])
boyt.shutdown()
