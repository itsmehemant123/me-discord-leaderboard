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
    async def initialize(self, ctx):
        logging.info('Start configuration for server:' + ctx.message.server.id)
        
        discord_server = ctx.message.server
        discord_user = ctx.message.author

        db_user = self.session.query(User).filter(User.discord_id == discord_user.id).first()
        db_server = self.session.query(Server).filter(Server.discord_id == discord_server.id).first()

        if (db_user is None):
            new_user = User(discord_user.id, discord_user.name, discord_user.display_name)
            self.session.add(new_user)

        if (db_server is None):
            db_status = self.session.query(Status).join(Server).filter(Server.discord_id == discord_server.id).first()
            if (db_status is not None): self.session.delete(db_status)

            new_server = Server(discord_server.id, discord_server.name, '', '', '', '')
            new_status = Status(0, new_user, new_server)
            self.session.add(new_server)
            self.session.add(new_status)
        
        self.session.commit()
        await self.bot.send_message(ctx.message.channel, 'Started bot configuration for this server.')
        await self.bot.send_message(ctx.message.channel, 'Use `!configstatus` to check the status, and set them with `!set <param> <value>`.')

    @commands.command(pass_context=True, no_pm=True)
    async def configstatus(self, ctx):
        if (not await self.check_and_dismiss(ctx, True)): return
        
        server_configuration = ''
        server = self.session.query(Server).filter(Server.discord_id == ctx.message.server.id).first()

        if (server.channel == ''): 
            server_configuration += 'Channel not set. Do `!set chan #<channelname>`\n'
        else:
            server_configuration += 'Channel: ' + server.channel + '\n'
        if (server.rx1 == ''): 
            server_configuration += 'Upvote emoji not set. Do `!set up <emoji>`\n'
        else:
            server_configuration += 'Upvote emoji: ' + server.rx1 + '\n'
        if (server.rx2 == ''): 
            server_configuration += 'Downvote emoji not set. Do `!set down <emoji>`\n'
        else:
            server_configuration += 'Downvote amoji: ' + server.rx2 + '\n'

        await self.bot.send_message(ctx.message.channel, server_configuration)
        logging.info('CONFIGSTATUS')
    
    @commands.command(pass_context=True, no_pm=True)
    async def set(self, ctx, attribute: str, val: str):
        if (not await self.check_and_dismiss(ctx, True)): return

        status = self.session.query(Status).join(Server).filter(Server.discord_id == ctx.message.server.id).first()
        if (status.user.discord_id is not ctx.message.author.id and status.server_status is not 2):
            self.bot.send_message(ctx.message.channel, 'Only the user (' + status.user.display_name + ') who started the configuration can set.')

        server_configuration = ''
        server = self.session.query(Server).filter(Server.discord_id == ctx.message.server.id).first()

        if (attribute == 'chan'):
            server.channel = val
        elif (attribute == 'up'):
            server.rx1 = val
        elif (attribute == 'down'):
            server.rx2 = val

        if (server.channel == ''): server_configuration += 'Channel not set. Do `!set chan #<channelname>`\n'
        if (server.rx1 == ''): server_configuration += 'Upvote emoji not set. Do `!set up <emoji>`\n'
        if (server.rx2 == ''): server_configuration += 'Downvote emoji not set. Do `!set down <emoji>`\n'

        if (server_configuration == ''):
            status.server_status = 2
        else:
            status.server_status = 1

        self.session.commit()
        if (server_configuration is not ''): await self.bot.send_message(ctx.message.channel, server_configuration)
        logging.info('SET')

    @commands.command(pass_context=True, no_pm=True)
    async def save(self, ctx):
        if (not await self.check_and_dismiss(ctx)): return
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def abort(self, ctx):
        if (not await self.check_and_dismiss(ctx)): return
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def stats(self, ctx):
        if (not await self.check_and_dismiss(ctx)): return
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def top(self, ctx):
        if (not await self.check_and_dismiss(ctx)): return
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def bottom(self, ctx):
        if (not await self.check_and_dismiss(ctx)): return
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def test(self, ctx):
        if (not await self.check_and_dismiss(ctx)): return
        logging.info('lol')

    async def check_and_dismiss(self, ctx, is_being_configured=False):
        is_set = self.check_status(ctx.message.server.id, is_being_configured)
        if (not is_set): 
            await self.bot.send_message(ctx.message.channel, 'Bot not configured yet. Run `!configure` to get started.')
        
        return is_set

    def check_status(self, server_id, is_being_configured):
        status = self.session.query(Status).join(Server).filter(Server.discord_id == server_id).first()
        
        if (status is None): return False

        if (is_being_configured): return True
        if (status.server_status is not 2): return False
        
        return True

    def shutdown(self):
        self.session.close()
