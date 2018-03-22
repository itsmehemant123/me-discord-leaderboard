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
from discord import utils
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
        
    def write_to_db(self, messages):
        for message in messages:
            rxns = message.reactions
            user = message.author
            print(rxns)


    async def download_messages(self, channel, limit, current_count, last_msg, msg_handle):
        before = None
        dwnld_limit = 100

        if last_msg is not None:
            before = last_msg

        if (current_count >= limit):
            await self.bot.edit_message(msg_handle, 'Finished downloading messages.')
            return current_count

        batch_size = 0
        msg_set = []
        async for message in self.bot.logs_from(channel, limit=dwnld_limit, before=before):
            batch_size += 1
            last_msg = message
            msg_set.append(message)

        self.write_to_db(msg_set)

        if (current_count % 1000 == 0):
            await self.bot.edit_message(msg_handle, 'Downloaded ' + str(current_count) + ' messages.')

        current_count += batch_size
        if batch_size < 100:
            await self.bot.edit_message(msg_handle, 'Finished downloading messages.')
            return current_count
        else:
            return current_count + await self.download_messages(channel, limit, current_count, last_msg, msg_handle)

    @commands.command(pass_context=True, no_pm=True)
    async def init(self, ctx):
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
    async def check(self, ctx):
        if (not await self.check_and_dismiss(ctx, True)): return
        
        server_configuration = ''
        server = self.session.query(Server).filter(Server.discord_id == ctx.message.server.id).first()

        if (server.channel == ''): 
            server_configuration += 'Channel not set. Do `!set chan #<channelname>`\n'
        else:
            server_configuration += 'Channel: <#' + server.channel + '>\n'
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
            server.channel = re.sub('[<#>]', '', val)
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
        else: await self.bot.send_message(ctx.message.channel, 'Finished configuring bot for this server.')
        logging.info('SET')

    @commands.command(pass_context=True, no_pm=True)
    async def populate(self, ctx):
        if (not await self.check_and_dismiss(ctx)):
            return
        server = self.session.query(Server).filter(Server.discord_id == ctx.message.server.id).first()
        channel = discord.utils.get(ctx.message.server.channels, id=server.channel)
        logging.info('Issued download in: ' + channel.name + '.')
        resp = await self.bot.send_message(ctx.message.channel, 'Downloading messages.')
        
        await self.download_messages(channel, 20000, 0, None, resp)
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def stats(self, ctx):
        if (not await self.check_and_dismiss(ctx)): return
        logging.info('lol')

    @commands.command(pass_context=True, no_pm=True)
    async def top(self, ctx, channel: discord.Channel):
        if (not await self.check_and_dismiss(ctx)): return
        print(channel.id + ':' + channel.name)
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
