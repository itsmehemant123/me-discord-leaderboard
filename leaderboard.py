import re
import io
import sys
import json
import time
import discord
from discord.ext import commands
from datetime import datetime, timedelta
from string import ascii_letters
from scipy.stats import beta
from os import listdir
from os.path import isfile, join
from discord.ext import commands
from discord import utils
from models.base import Session, engine, Base
from models.servers import Server
from models.users import User
from models.status import Status
from models.messages import Message
from models.nicknames import Nickname
from sqlalchemy import func, cast, Float
import logging


class LeaderBoyt(commands.Cog):

    def __init__(self, bot):
        logging.basicConfig(level=logging.INFO)
        Base.metadata.create_all(engine, checkfirst=True)

        self.stat_dist_data = None
        self.session = Session()
        self.bot = bot

    def parse_messages(self, messages, temp_cache):
        for message in messages:
            current_user = message.author
            current_message = message.content
            current_message_id = message.id
            current_user_index = -1
            current_user_in_db = False

            if (current_message is None or current_message == ''):
                current_message = '\n'.join(
                    [i['url'] for i in message.attachments])

            if (current_user.id not in temp_cache['user_keys']):
                current_user_index = len(temp_cache['new_users'])
                temp_cache['new_users'].append(current_user)
                temp_cache['user_keys'].append(current_user.id)
            else:
                current_user_index = [i for i, d in enumerate(
                    temp_cache['new_users']) if d.id == current_user.id]
                if (len(current_user_index) == 0):
                    current_user_in_db = True
                else:
                    current_user_index = current_user_index[0]

            if (message.id not in temp_cache['message_keys']):
                temp_cache['new_messages'].append({'id': message.id, 'content': current_message, 'timestamp': message.timestamp, 'rxns': message.reactions,
                                                   'discord_id': current_message_id, 'user_index': current_user_index, 'user_in_db': current_user_in_db, 'author': current_user})

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
                msg_user = self.session.query(User).filter(
                    User.discord_id == str(message['author'].id)).first()
                user_cache[message['author'].id] = msg_user
            elif (message['user_in_db']):
                msg_user = user_cache[message['author'].id]
            else:
                msg_user = new_users[message['user_index']]

            rx1 = [d for d in message['rxns'] if str(d.emoji) == server.rx1]
            rx2 = [d for d in message['rxns'] if str(d.emoji) == server.rx2]

            if(len(rx1) == 0 or len(rx2) == 0):
                logging.info('Skipping due to no reactions.')
                continue
            else:
                rx1, rx2 = rx1[0], rx2[0]

            new_message = Message(message['id'], temp_cache['server'], msg_user,
                                  message['content'], message['timestamp'], rx1.count, rx2.count)
            self.session.add(new_message)

        self.session.commit()
        # await self.bot.send_message(temp_cache['ctx'].message.channel, 'Wrote messages to the database.')

        logging.info('Writing to database')

    @commands.command(pass_context=True, no_pm=True)
    async def init(self, ctx):
        logging.info('Start configuration for server:' + ctx.message.guild.id)

        discord_server = ctx.message.guild
        discord_user = ctx.message.author

        db_user = self.session.query(User).filter(
            User.discord_id == str(discord_user.id)).first()
        db_server = self.session.query(Server).filter(
            Server.discord_id == str(discord_server.id)).first()
        db_status = self.session.query(Status).join(Server).filter(
            Server.discord_id == str(ctx.message.guild.id)).first()

        if ((db_status is not None and db_status.server_status == 2) and not (ctx.message.author.id == db_status.user.discord_id)):
            logging.info('Attemted to init the server, aborting')
            await ctx.send('Only ' + db_status.user.user_name + ' can initialize the bot again')
            return

        if (db_user is None):
            new_user = User(discord_user.id, discord_user.name,
                            discord_user.display_name)
            self.session.add(new_user)
            db_user = new_user

        if (db_server is None):
            db_status = self.session.query(Status).join(Server).filter(
                Server.discord_id == str(discord_server.id)).first()
            if (db_status is not None):
                self.session.delete(db_status)

            new_server = Server(discord_server.id,
                                discord_server.name, '', '', '', '')
            new_status = Status(0, db_user, new_server)
            self.session.add(new_server)
            self.session.add(new_status)

        self.session.commit()
        await ctx.send('Started bot configuration for this server.')
        await ctx.send('Use `!check` to check the status, and set them with `!set <param> <value>`.')
        await ctx.send('If using emojis not in this server, use the fully qualified name, eg `<:downvote:335141916989456384>` while setting `up` and `down`.')

    @commands.command(pass_context=True, no_pm=True)
    async def check(self, ctx):
        if (not await self.check_and_dismiss(ctx, True)):
            return

        server_configuration = ''
        server = self.session.query(Server).filter(
            Server.discord_id == str(ctx.message.guild.id)).first()

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
            server_configuration += 'Downvote emoji: ' + server.rx2 + '\n'

        await ctx.send(server_configuration)
        logging.info('Check status.')

    @commands.command(pass_context=True, no_pm=True)
    async def set(self, ctx, attribute: str, val: str):
        if (not await self.check_and_dismiss(ctx, True)):
            return

        status = self.session.query(Status).join(Server).filter(
            Server.discord_id == str(ctx.message.guild.id)).first()
        if (not(status.user.discord_id == str(ctx.message.author.id)) and not(status.server_status == 2)):
            ctx.send('Only the user (' + status.user.display_name +
                     ') who started the configuration can set.')
            return

        db_status = self.session.query(Status).join(Server).filter(
            Server.discord_id == str(ctx.message.guild.id)).first()
        if ((db_status is not None and db_status.server_status == 2) and not (ctx.message.author.id == db_status.user.discord_id)):
            logging.info('Attemted to init the server, aborting')
            await ctx.send('Only ' + db_status.user.user_name + ' can initialize the bot again')
            return

        server_configuration = ''
        server = self.session.query(Server).filter(
            Server.discord_id == str(ctx.message.guild.id)).first()

        if (attribute == 'chan'):
            server.channel = re.sub('[<#>]', '', val)
        elif (attribute == 'up'):
            server.rx1 = val
        elif (attribute == 'down'):
            server.rx2 = val

        if (server.channel == ''):
            server_configuration += 'Channel not set. Do `!set chan #<channelname>`\n'
        if (server.rx1 == ''):
            server_configuration += 'Upvote emoji not set. Do `!set up <emoji>`\n'
        if (server.rx2 == ''):
            server_configuration += 'Downvote emoji not set. Do `!set down <emoji>`\n'

        if (server_configuration == ''):
            status.server_status = 2
        else:
            status.server_status = 1

        self.session.commit()
        if (not(server_configuration == '')):
            await ctx.send(server_configuration)
        else:
            await ctx.send('Finished configuring bot for this server.')
        logging.info('Set ' + attribute + ' as ' + val + '.')

    @commands.command(pass_context=True, no_pm=True)
    async def populate(self, ctx, count):
        if (not await self.check_and_dismiss(ctx)):
            return
        db_server = self.session.query(Server).filter(
            Server.discord_id == str(ctx.message.guild.id)).first()

        temp_cache = {}
        temp_cache['server'] = db_server
        temp_cache['new_messages'] = []
        temp_cache['new_users'] = []
        temp_cache['ctx'] = ctx

        temp_cache['message_keys'] = [key[0] for key in self.session.query(
            Message.discord_id).filter(Message.server_id == db_server.id).all()]
        temp_cache['user_keys'] = [key[0]
                                   for key in self.session.query(User.discord_id).all()]
        logging.info('MSG COUNT:' + str(len(temp_cache['message_keys'])))
        logging.info('USR COUNT:' + str(len(temp_cache['user_keys'])))

        channel = discord.utils.get(
            ctx.message.guild.channels, id=db_server.channel)
        logging.info('Issued download in: ' + channel.name + '.')
        resp = await ctx.send('Downloading messages.')

        await self.download_messages(channel, int(count), 0, None, resp, temp_cache)
        await self.write_to_db(temp_cache)
        logging.info('Populate the database with data from ' +
                     str(db_server.discord_id) + ':' + db_server.name)

    @commands.command(pass_context=True, no_pm=True)
    async def top(self, ctx, lim: str = '10'):
        if (not await self.check_and_dismiss(ctx)):
            return

        is_span = False
        if (not self.is_int(lim)):
            is_span = True

        await ctx.send(embed=self.generate_memer_board(ctx, 'number_up', lim, is_span))
        logging.info('Get top memers.')

    @commands.command(pass_context=True, no_pm=True)
    async def bottom(self, ctx, lim: str = '10'):
        if (not await self.check_and_dismiss(ctx)):
            return

        is_span = False
        if (not self.is_int(lim)):
            is_span = True

        await ctx.send(embed=self.generate_memer_board(ctx, 'number_down', lim, is_span))
        logging.info('Get shit memers.')

    @commands.command(pass_context=True, no_pm=True)
    async def ptop(self, ctx, lim: str = '10'):
        if (not await self.check_and_dismiss(ctx)):
            return

        is_span = False
        if (not self.is_int(lim)):
            is_span = True

        await ctx.send(embed=self.generate_memer_board(ctx, '%_up', lim, is_span))
        logging.info('Get Top % memers.')

    @commands.command(pass_context=True, no_pm=True)
    async def pbottom(self, ctx, lim: str = '10'):
        if (not await self.check_and_dismiss(ctx)):
            return

        is_span = False
        if (not self.is_int(lim)):
            is_span = True

        await ctx.send(embed=self.generate_memer_board(ctx, '%_down', lim, is_span))
        logging.info('Get Shit % memers.')

    @commands.command(pass_context=True, no_pm=True)
    async def atop(self, ctx, lim: str = '10'):
        if (not await self.check_and_dismiss(ctx)):
            return

        is_span = False
        if (not self.is_int(lim)):
            is_span = True

        await ctx.send(embed=self.generate_memer_board(ctx, 'avg_up', lim, is_span))
        logging.info('Get Top avg memers.')

    @commands.command(pass_context=True, no_pm=True)
    async def abottom(self, ctx, lim: str = '10'):
        if (not await self.check_and_dismiss(ctx)):
            return

        is_span = False
        if (not self.is_int(lim)):
            is_span = True

        await ctx.send(embed=self.generate_memer_board(ctx, 'avg_down', lim, is_span))
        logging.info('Get Shit avg memers.')

    @commands.command(pass_context=True, no_pm=True)
    async def btop(self, ctx, lim: str = '10'):
        if (not await self.check_and_dismiss(ctx)):
            return

        is_span = False
        if (not self.is_int(lim)):
            is_span = True

        await ctx.send(embed=self.generate_memer_board(ctx, 'beta_top', lim, is_span))
        logging.info('Get Top memers by beta dist.')

    @commands.command(pass_context=True, no_pm=True)
    async def bbottom(self, ctx, lim: str = '10'):
        if (not await self.check_and_dismiss(ctx)):
            return

        is_span = False
        if (not self.is_int(lim)):
            is_span = True

        await ctx.send(embed=self.generate_memer_board(ctx, 'beta_down', lim, is_span))
        logging.info('Get Shit memers by beta dist.')

    @commands.command(pass_context=True, no_pm=True)
    async def stats(self, ctx, target: str = ''):
        if (not await self.check_and_dismiss(ctx)):
            return

        if (target is ''):
            logging.info('CHeck for self')
            target = ctx.message.author.id
        else:
            logging.info('Checking for user ' + target)
            target = re.sub('[<@!>]', '', target)

        logging.info('Target: ' + target)
        db_user = self.session.query(User).filter(
            User.discord_id == str(target)).first()
        db_server = self.session.query(Server).filter(
            Server.discord_id == str(ctx.message.guild.id)).first()

        if (db_server is None):
            await ctx.send('Bot not initialized in server.')
            return

        if (db_user is None):
            await ctx.send('No data on user.')
            db_user = User(ctx.message.author.id, ctx.message.author.name,
                           ctx.message.author.display_name)
            self.session.add(db_user)
            self.session.commit()
            return

        db_nick = self.session.query(Nickname).filter(
            Nickname.user_id == db_user.id, Nickname.server_id == db_server.id).first()

        if (db_nick is None or db_nick.display_name == ''):
            nickname = db_user.display_name
        else:
            nickname = db_nick.display_name

        total_doots = self.session.query(func.sum(Message.rx1_count), func.sum(Message.rx2_count), func.avg(Message.rx1_count), func.avg(Message.rx2_count)).filter(
            Message.server_id == db_server.id, Message.user_id == db_user.id).group_by(Message.user_id).first()
        total_memes = self.session.query(Message.id).filter(
            Message.server_id == db_server.id, Message.user_id == db_user.id).count()

        board_embed = discord.Embed(
            title='Statistics for ' + nickname + ' for a total of ' + str(total_memes) + ' memes')
        board_embed.set_author(name='LeaderBOYT', url='https://github.com/itsmehemant123/me-discord-leaderboard',
                               icon_url='https://photos.hd92.me/images/2018/03/23/martin-shkreli.png')

        metric_list = 'Total Upvotes\nTotal Downvotes\nAverage # of Upvotes\nAverage # of Downvotes\n%ge of Upvotes'
        stat_list = str(total_doots[0]) + '\n' + \
            str(total_doots[1]) + '\n' + '%.2f' % (total_doots[2]) + '\n' + \
            '%.2f' % (total_doots[3]) + '\n' + '%.2f' % ((total_doots[0] /
                                                          (total_doots[0] + total_doots[1])) * 100) + ' %'

        board_embed.add_field(name='Metric', value=metric_list, inline=True)
        board_embed.add_field(name='Stats', value=stat_list, inline=True)
        await ctx.send(embed=board_embed)
        logging.info('Checking stats.')

    @commands.command(pass_context=True, no_pm=True)
    async def test(self, ctx):
        if (not await self.check_and_dismiss(ctx)):
            return
        logging.info('lol')

    def generate_memer_board(self, ctx, method, lim, span):
        current_server = ctx.message.guild
        db_server = self.session.query(Server).filter(
            Server.discord_id == str(current_server.id)).first()
        if (db_server is None):
            return

        message_count = 10
        start_date = datetime.now()

        if (not span):
            message_count = int(lim)
            start_date = datetime.min
        elif (lim == '1d'):
            start_date = start_date - timedelta(hours=24)
        elif (lim == '1w'):
            start_date = start_date - timedelta(weeks=1)
        elif (lim == '1m'):
            start_date = start_date - timedelta(weeks=4)
        else:
            start_date = start_date - timedelta(weeks=52)

        if (message_count > 10):
            message_count = 10  # Until rich embeds are switched for generic messages

        heading = 'Memers'

        if (method == 'number_up'):
            memers = self.session.query(Message.user_id, func.sum(Message.rx1_count)).filter(Message.server_id == db_server.id, Message.created_at > start_date).group_by(
                Message.user_id).order_by(func.sum(Message.rx1_count).desc()).limit(message_count).all()
            heading = 'Top ' + heading
        elif (method == 'number_down'):
            memers = self.session.query(Message.user_id, func.sum(Message.rx2_count)).filter(Message.server_id == db_server.id, Message.created_at > start_date).group_by(
                Message.user_id).order_by(func.sum(Message.rx2_count).desc()).limit(message_count).all()
            heading = 'Shit ' + heading
        elif (method == '%_up'):
            memers = self.session.query(Message.user_id, cast(func.sum(Message.rx1_count), Float) / (cast(func.sum(Message.rx1_count), Float) + cast(func.sum(Message.rx2_count), Float)), func.sum(Message.rx1_count), func.sum(
                Message.rx2_count)).filter(Message.server_id == db_server.id, Message.created_at > start_date).group_by(Message.user_id).order_by((cast(func.sum(Message.rx1_count), Float) / (cast(func.sum(Message.rx1_count), Float) + cast(func.sum(Message.rx2_count), Float))).desc()).limit(message_count).all()
            heading = 'Top ' + heading
        elif (method == '%_down'):
            memers = self.session.query(Message.user_id, cast(func.sum(Message.rx1_count), Float) / (cast(func.sum(Message.rx1_count), Float) + cast(func.sum(Message.rx2_count), Float)), func.sum(Message.rx1_count), func.sum(
                Message.rx2_count)).filter(Message.server_id == db_server.id, Message.created_at > start_date).group_by(Message.user_id).order_by((cast(func.sum(Message.rx1_count), Float) / (cast(func.sum(Message.rx1_count), Float) + cast(func.sum(Message.rx2_count), Float))).asc()).limit(message_count).all()
            heading = 'Shit ' + heading
        elif (method == 'avg_up'):
            memers = self.session.query(Message.user_id, func.avg(Message.rx1_count)).filter(Message.server_id == db_server.id, Message.created_at > start_date).group_by(
                Message.user_id).order_by(func.avg(Message.rx1_count).desc()).limit(message_count).all()
            heading = 'Top ' + heading + ' by average'
        elif (method == 'avg_down'):
            memers = self.session.query(Message.user_id, func.avg(Message.rx2_count)).filter(Message.server_id == db_server.id, Message.created_at > start_date).group_by(
                Message.user_id).order_by(func.avg(Message.rx2_count).desc()).limit(message_count).all()
            heading = 'Shit ' + heading + ' by average'
        elif (method == 'beta_top'):
            if (self.stat_dist_data is None or (datetime.now() - self.stat_dist_data['timestamp']).days > 14):
                self.refresh_beta_dist(db_server)
            memers = self.session.query(Message.user_id, (cast(func.sum(Message.rx1_count), Float) + self.stat_dist_data['alpha']) / (cast(func.sum(Message.rx1_count), Float) + cast(func.sum(Message.rx2_count), Float) + self.stat_dist_data['alpha'] + self.stat_dist_data['beta'])).filter(
                Message.server_id == db_server.id, Message.created_at > start_date).group_by(Message.user_id).order_by(((cast(func.sum(Message.rx1_count), Float) + self.stat_dist_data['alpha']) / (cast(func.sum(Message.rx1_count), Float) + cast(func.sum(Message.rx2_count), Float) + self.stat_dist_data['alpha'] + self.stat_dist_data['beta'])).desc()).limit(message_count).all()
            heading = 'Top ' + heading + ' by beta distribution'
        else:  # if (method == 'beta_down'):
            if (self.stat_dist_data is None or (datetime.now() - self.stat_dist_data['timestamp']).days > 14):
                self.refresh_beta_dist(db_server)
            memers = self.session.query(Message.user_id, (cast(func.sum(Message.rx1_count), Float) + self.stat_dist_data['alpha']) / (cast(func.sum(Message.rx1_count), Float) + cast(func.sum(Message.rx2_count), Float) + self.stat_dist_data['alpha'] + self.stat_dist_data['beta'])).filter(
                Message.server_id == db_server.id, Message.created_at > start_date).group_by(Message.user_id).order_by(((cast(func.sum(Message.rx1_count), Float) + self.stat_dist_data['alpha']) / (cast(func.sum(Message.rx1_count), Float) + cast(func.sum(Message.rx2_count), Float) + self.stat_dist_data['alpha'] + self.stat_dist_data['beta'])).asc()).limit(message_count).all()
            heading = 'Shit ' + heading + ' by beta distribution'

        board_embed = discord.Embed(title='Leaderboard')
        board_embed.set_author(name='LeaderBOYT', url='https://github.com/itsmehemant123/me-discord-leaderboard',
                               icon_url='https://photos.hd92.me/images/2018/03/23/martin-shkreli.png')

        user_list = ''
        stat_list = ''

        for ind, memer in enumerate(memers):
            user = self.session.query(User).filter(User.id == memer[0]).first()
            nick = self.session.query(Nickname).filter(
                Nickname.user_id == memer[0], Nickname.server_id == db_server.id).first()
            if (nick is None or nick.display_name == ''):
                nickname = user.display_name
            else:
                nickname = nick.display_name

            if (nickname is None):
                nickname = '<banned user>'

            user_list += str(ind + 1) + ') ' + nickname + '\n'
            if (method == 'number_up'):
                stat_list += str(memer[1]) + ' ' + db_server.rx1 + '\n'
            elif (method == 'number_down'):
                stat_list += str(memer[1]) + ' ' + db_server.rx2 + '\n'
            elif (method == '%_up' or method == '%_down'):
                stat_list += '%.2f' % (memer[1] * 100) + '% ' + \
                    db_server.rx1 + '/' + db_server.rx2 + '\n'
            elif (method == 'avg_up'):
                stat_list += '%.2f' % (memer[1]) + \
                    ' ' + db_server.rx1 + '\n'
            elif (method == 'avg_down'):
                stat_list += '%.2f' % (memer[1]) + \
                    ' ' + '\n'
            elif (method == 'beta_top' or method == 'beta_down'):
                stat_list += '%.2f' % (memer[1] * 100) + '% ' + \
                    ' Quality\n'

        board_embed.add_field(name=heading, value=user_list, inline=True)
        board_embed.add_field(name='Stats', value=stat_list, inline=True)

        return board_embed

    async def readmeme(self, message):
        logging.info('Processing incoming meme.')
        current_user = message.author
        current_server = message.guild

        if (current_server is None or current_user is None):
            logging.info('Missing info. Discarding.')
            return

        db_server = self.session.query(Server).filter(
            Server.discord_id == str(current_server.id)).first()
        if (db_server is None):
            return
        if (not self.is_correct_channel_and_message(message, db_server)):
            logging.info('Not in selected channel. Discarding.')
            return

        db_user = self.session.query(User).filter(
            User.discord_id == str(current_user.id)).first()
        if (db_user is None):
            db_user = User(current_user.id, current_user.name,
                           current_user.display_name)
            self.session.add(db_user)

        content = self.get_message_content(message)

        self.session.add(Message(message.id, db_server,
                                 db_user, content, message.timestamp, 1, 1))
        self.session.commit()
        logging.info('Wrote new meme.')

    async def add_reaction(self, reaction, user):
        self.update_reactions(reaction, user)
        logging.info('Add reaction.')

    async def remove_reaction(self, reaction, user):
        self.update_reactions(reaction, user)
        logging.info('Remove reaction.')

    async def clear_reaction(self, message, reactions):
        db_message = self.session.query(Message).filter(
            Message.discord_id == str(message.id)).first()
        if (db_message is None):
            return

        db_message.rx1_count = 0
        db_message.rx2_count = 0
        self.session.commit()
        logging.info('Clear reaction.')

    async def check_and_dismiss(self, ctx, is_being_configured=False):
        is_set = self.check_status(ctx.message.guild.id, is_being_configured)
        if (not is_set):
            await ctx.send('Bot not configured yet. Run `!init` to get started.')

        return is_set

    def update_reactions(self, reaction, user):
        current_user = user
        current_message = reaction.message
        current_server = reaction.message.guild

        db_server = self.session.query(Server).filter(
            Server.discord_id == str(current_server.id)).first()
        if (db_server is None):
            # Lol, gotem
            logging.info('Server not found, bot not configured for: ' +
                         str(current_server.id) + ':' + current_server.name)
            return
        if (not self.is_correct_channel_and_message(current_message, db_server)):
            return

        db_user = self.session.query(User).filter(
            User.discord_id == str(current_user.id)).first()
        if (db_user is None):
            db_user = User(current_user.id, current_user.name,
                           current_user.display_name)
            self.session.add(db_user)

        db_message = self.session.query(Message).filter(
            Message.discord_id == str(current_message.id)).first()
        if (db_message is None):
            content = self.get_message_content(current_message)
            db_message = Message(str(current_message.id), db_server,
                                 db_user, content, current_message.timestamp, 0, 0)
            self.session.add(db_message)

        if (str(reaction.emoji) == db_server.rx1):
            db_message.rx1_count = reaction.count
        elif (str(reaction.emoji) == db_server.rx2):
            db_message.rx2_count = reaction.count

        self.session.commit()
        logging.info('Updated reactions.')

    def update_nickname(self, before, after):
        if (after.nick is None):
            logging.info('Not a nick update, skipping.')
            return
        db_user = self.session.query(User).filter(
            User.discord_id == str(before.id)).first()
        db_server = self.session.query(Server).filter(
            Server.discord_id == str(before.guild.id)).first()

        if (db_server is None):
            logging.info(
                'Update nick attempt on uninitialized server, aborting.')
            return

        if (db_user is None):
            new_user = User(after.id, after.name,
                            after.nick)
            self.session.add(new_user)
            db_user = new_user

        db_nickname = self.session.query(Nickname).filter(
            Nickname.user_id == db_user.id, Nickname.server_id == db_server.id).first()
        if (db_nickname is None):
            new_nick = Nickname(db_user, db_server, after.display_name)
            self.session.add(new_nick)
        else:
            db_nickname.display_name = after.display_name

        self.session.commit()
        logging.info('Updated nickname')

    def is_correct_channel_and_message(self, message, server):
        if (not (server.channel == str(message.channel.id))):
            return False

        current_message = self.get_message_content(message)
        if (not (current_message.startswith("http") and "/" in current_message and "." in current_message and " " not in current_message)):
            # stolen from dino
            return False

        return True

    def get_message_content(self, message):
        content = message.content
        if (content == '' or content is None):
            content = '\n'.join([i['url'] for i in message.attachments])

        return content

    def check_status(self, server_id, is_being_configured):
        status = self.session.query(Status).join(Server).filter(
            Server.discord_id == str(server_id)).first()

        if (status is None):
            return False

        if (is_being_configured):
            return True
        if (not(status.server_status == 2)):
            return False

        return True

    def refresh_beta_dist(self, db_server):
        self.stat_dist_data = {}

        startdate = datetime.now() - timedelta(weeks=4)
        total_averages = self.session.query(Message.user_id, func.sum(cast(Message.rx1_count, Float)) / func.sum(cast(Message.rx1_count + Message.rx2_count, Float))).filter(
            Message.server_id == db_server.id, Message.created_at < startdate).group_by(Message.user_id).all()
        average_list = [round(aver[1], 3) for aver in total_averages]
        beta_stats = beta.fit(average_list)

        self.stat_dist_data['alpha'], self.stat_dist_data['beta'], self.stat_dist_data['lower'], self.stat_dist_data['scale'] = beta_stats
        self.stat_dist_data['data'] = total_averages
        self.stat_dist_data['timestamp'] = datetime.now()

    def is_int(self, val):
        try:
            int(val)
            return True
        except ValueError:
            return False

    def shutdown(self):
        self.session.close()
