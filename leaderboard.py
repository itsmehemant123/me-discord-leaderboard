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
        
    def parse_messages(self, messages, temp_cache):
        for message in messages:
            current_user = message.author
            current_message = message.content
            current_message_id = message.id
            current_user_index = -1
            current_user_in_db = False

            if (current_message is None or current_message is ''):
                current_message = '\n'.join([i['url'] for i in message.attachments])

            if (current_user.id not in temp_cache['user_keys']):
                current_user_index = len(temp_cache['new_users'])
                temp_cache['new_users'].append(current_user)
                temp_cache['user_keys'].append(current_user.id)
            else:
                current_user_index = [i for i,d in enumerate(temp_cache['new_users']) if d['id'] == current_user.id]
                if (len(current_user_index) == 0):
                    current_user_in_db = True
                else:
                    current_user_index = current_user_index[0]
            
            if (message.id not in temp_cache['message_keys']):
                temp_cache['new_messages'].append({'id': message.id, 'content': current_message, 'timestamp': message.timestamp, 'rxns': message.reactions, 'discord_id': current_message_id, 'user_index': current_user_index, 'user_in_db': current_user_in_db, 'author': current_user})
            
    async def download_messages(self, channel, limit, current_count, last_msg, msg_handle, temp_cache):
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

        self.parse_messages(msg_set, temp_cache)

        if (current_count % 1000 == 0):
            await self.bot.edit_message(msg_handle, 'Downloaded ' + str(current_count) + ' messages.')

        current_count += batch_size
        if batch_size < 100:
            await self.bot.edit_message(msg_handle, 'Finished downloading messages.')
            return current_count
        else:
            return current_count + await self.download_messages(channel, limit, current_count, last_msg, msg_handle, temp_cache)
    
    async def write_to_db(self, temp_cache):
        new_users = []
        user_cache = {}
        server = temp_cache['server']

        for user in temp_cache['new_users']:
            new_user = User(user.id, user.name, user.display_name)
            self.session.add(new_user)
            new_users.append(new_user)
        
        for message in temp_cache['new_messages']:
            if (message['user_in_db'] and message['author'].id not in user_cache):
                msg_user = self.session.query(User).filter(User.discord_id == message['author'].id).first()
                user_cache[message['author'].id] = msg_user
            elif (message['user_in_db']):
                msg_user = user_cache[message['author'].id]
            else:
                msg_user = new_users[message['user_index']]

            rx1 = [d for d in message['rxns'] if d.emoji == server.rx1]
            rx2 = [d for d in message['rxns'] if d.emoji == server.rx2]

            if(len(rx1) == 0 or len(rx2) == 0):
                continue
            else:
                rx1, rx2 = rx1[0], rx2[0]
            
            new_message = Message(message['id'], temp_cache['server'], msg_user, message['content'], message['timestamp'], rx1.count, rx2.count)
            self.session.add(new_message)

        self.session.commit()
        await self.bot.send_message(temp_cache['ctx'].message.channel, 'Wrote messages to the database.')

        logging.info('Writing to database')

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
        await self.bot.send_message(ctx.message.channel, 'Use `!check` to check the status, and set them with `!set <param> <value>`.')

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
        db_server = self.session.query(Server).filter(Server.discord_id == ctx.message.server.id).first()
        
        temp_cache = {}
        temp_cache['server'] = db_server
        temp_cache['new_messages'] = []
        temp_cache['new_users'] = []
        temp_cache['ctx'] = ctx

        temp_cache['message_keys'] = [key[0] for key in self.session.query(Message.discord_id).filter(Message.server_id == db_server.id).all()]
        temp_cache['user_keys'] = [key[0] for key in self.session.query(User.discord_id).all()]
        logging.info('MSG COUNT:' + str(len(temp_cache['message_keys'])))
        logging.info('USR COUNT:' + str(len(temp_cache['user_keys'])))
        
        channel = discord.utils.get(ctx.message.server.channels, id=db_server.channel)
        logging.info('Issued download in: ' + channel.name + '.')
        resp = await self.bot.send_message(ctx.message.channel, 'Downloading messages.')
        
        await self.download_messages(channel, 20000, 0, None, resp, temp_cache)
        await self.write_to_db(temp_cache)
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

    async def readmeme(self, message):
        logging.info('Writing incoming meme to db.')
        current_user = message.author
        current_server = message.server

        if (current_server is None or current_user is None):
            return
        
        db_server = self.session.query(Server).filter(Server.discord_id == current_server.id).first()
        if (db_server is None): return

        db_user = self.session.query(User).filter(User.discord_id == current_user.id).first()
        if (db_user is None):
            db_user = User(current_user.id, current_user.name, current_user.display_name)
            self.session.add(db_user)

        content = self.get_message_content(message)

        self.session.add(Message(message.id, db_server, db_user, content, message.timestamp, 0, 0))
        self.session.commit()
        logging.info('Wrote new meme.')

    async def add_reaction(self, reaction, user):
        self.update_reactions(reaction, user)
        logging.info('Add reaction.')

    async def remove_reaction(self, reaction, user):
        self.update_reactions(reaction, user)
        logging.info('Remove reaction.')

    async def clear_reaction(self, message, reactions):
        db_message = self.session.query(Message).filter(Message.discord_id == str(message.id)).first()
        if (db_message is None):
            return
        
        db_message.rx1_count = 0
        db_message.rx2_count = 0
        self.session.commit()
        logging.info('Clear reaction.')

    async def check_and_dismiss(self, ctx, is_being_configured=False):
        is_set = self.check_status(ctx.message.server.id, is_being_configured)
        if (not is_set): 
            await self.bot.send_message(ctx.message.channel, 'Bot not configured yet. Run `!init` to get started.')
        
        return is_set

    def update_reactions(self, reaction, user):
        current_user = user
        current_message = reaction.message
        current_server = reaction.message.server

        db_server = self.session.query(Server).filter(Server.discord_id == str(current_server.id)).first()
        if (db_server is None):
            # Lol, gotem
            logging.info('Server not found, bot not configured for: ' + str(current_server.id) + ':' + current_server.name)
            return

        db_user = self.session.query(User).filter(User.discord_id == str(current_user.id)).first()
        if (db_user is None):
            db_user = User(current_user.id, current_user.name, current_user.display_name)
            self.session.add(db_user)
        
        db_message = self.session.query(Message).filter(Message.discord_id == str(current_message.id)).first()
        if (db_message is None):
            content = self.get_message_content(current_message)
            db_message = Message(str(current_message.id), db_server, db_user, content, current_message.timestamp, 0, 0)
        
        if (reaction.emoji == db_server.rx1):
            db_message.rx1_count = reaction.count
        elif (reaction.emoji == db_server.rx2):
            db_message.rx2_count = reaction.count

        self.session.add(db_message)
        self.session.commit()
        logging.info('Updated reactions.')

    def get_message_content(self, message):
        content = message.content
        if (content is '' or content is None):
            content = '\n'.join([i['url'] for i in message.attachments])

        return content

    def check_status(self, server_id, is_being_configured):
        status = self.session.query(Status).join(Server).filter(Server.discord_id == server_id).first()
        
        if (status is None): return False

        if (is_being_configured): return True
        if (status.server_status is not 2): return False
        
        return True

    def shutdown(self):
        self.session.close()
