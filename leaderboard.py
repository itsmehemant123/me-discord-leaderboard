import re
import io
import sys
import json
import time
import discord
from string import ascii_letters
from os import listdir
from os.path import isfile, join
from discord.ext import commands
from models.base import Session, engine, Base
from models.servers import Server
from models.users import User
from models.status import Status
from models.messages import Message
import logging

class LeaderBoyt:

    def __init__(self, bot):
        logging.basicConfig(level=logging.INFO)
        Base.metadata.create_all(engine, checkfirst=True)

        self.session = Session()
        self.bot = bot
        
    # def write_to_yaml(self, messages):
    #     file_handle = open(self.wheatley_config['corpus-folder'] + str(time.time()) + '.yml', 'w+', encoding = 'utf-8')
    #     corpus_dict = {'categories': ['discord-chat'], 'conversations': []}
        
    #     for stim, resp in zip(messages[0::2], messages[1::2]):
    #         stim = self.ping_replace.sub('', stim.content).replace('\\', '\\\\')
    #         resp = self.ping_replace.sub('', resp.content).replace('\\', '\\\\')

    #         if (self.wheatley_config['max_dialog_length'] is not -1):
    #             stim = stim[:self.wheatley_config['max_dialog_length']]
    #             resp = resp[:self.wheatley_config['max_dialog_length']]

    #         corpus_dict['conversations'].append([stim, resp])

    #     file_handle.write(yaml.dump(corpus_dict, default_flow_style=False))
    #     file_handle.close()

    # async def download_messages(self, channel, limit, is_all, current_count, last_msg, msg_handle):
    #     before = None
    #     dwnld_limit = 100

    #     if last_msg is not None:
    #         before = last_msg

    #     if (not is_all and current_count >= limit):
    #         await self.bot.edit_message(msg_handle, 'Finished downloading messages.')
    #         return current_count

    #     batch_size = 0
    #     msg_set = []
    #     async for message in self.bot.logs_from(channel, limit=dwnld_limit, before=before):
    #         batch_size += 1
    #         last_msg = message
    #         msg_set.append(message)

    #     self.write_to_yaml(msg_set)

    #     if (current_count % 1000 == 0):
    #         await self.bot.edit_message(msg_handle, 'Downloaded ' + str(current_count) + ' messages.')

    #     current_count += batch_size
    #     if batch_size < 100:
    #         await self.bot.edit_message(msg_handle, 'Finished downloading messages.')
    #         return current_count
    #     else:
    #         return current_count + await self.download_messages(channel, limit, is_all, current_count, last_msg, msg_handle)

    # @commands.command(pass_context=True, no_pm=True)
    # async def prep_db(self, ctx, limit: str, channel: discord.Channel):
    #     if (len(set([role.name.lower() for role in ctx.message.author.roles]).intersection(set(self.admin_roles))) == 0):
    #         await self.bot.send_message(ctx.message.channel, 'Unauthorized to issue this command.')
    #         return
    #     logging.info('issued download with: ' + limit + ', in :' + channel.name + '.')
    #     resp = await self.bot.send_message(ctx.message.channel, 'Downloading messages.')
    #     is_all = False
    #     if (limit == 'all'):
    #         is_all = True
    #         limit = None
    #     else:
    #         limit = int(limit)
    #     await self.download_messages(channel, limit, is_all, 0, None, resp)

    @commands.command(pass_context=True, no_pm=True)
    async def configure(self, ctx):
        logging.info('Start configuration for server:' + ctx.message.server.id)
        discord_server = ctx.message.server
        # new_server = Server(discord_server.id)

    @commands.command(pass_context=True, no_pm=True)
    async def save(self, ctx):
        await self.check_and_dismiss(ctx)
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def abort(self, ctx):
        await self.check_and_dismiss(ctx)
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def stats(self, ctx):
        await self.check_and_dismiss(ctx)
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def top(self, ctx):
        await self.check_and_dismiss(ctx)
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def bottom(self, ctx):
        await self.check_and_dismiss(ctx)
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def test(self, ctx):
        await self.check_and_dismiss(ctx)
        logging.info('lol')

    async def check_and_dismiss(self, ctx):
        if (not self.check_status(ctx.message.server.id)): await self.bot.send_message(ctx.message.channel, 'Bot not configured yet. Run `!configure` to get started.')

    def check_status(self, server_id):
        status = self.session.query(Status).join(Server).filter(Server.discord_id == server_id).first()
        
        if (status is None): return False

        if (status.server_status is not 2): return False
        
        return True
