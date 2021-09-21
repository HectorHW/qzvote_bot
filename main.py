import os
import random
import string
import warnings

import telegram
from telegram.ext import Updater, Dispatcher, CallbackContext

from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

import json
import sys

from threading import Timer

def load_config(filename):
    if not os.path.exists(filename):
        return None

    with open(filename) as f:
        content = json.load(f)

    return content

def save_config(config, filename):
    with open(filename, 'w') as f:
        json.dump(config, f, sort_keys=True, indent=4)

if __name__ == '__main__':

    n_args = len(sys.argv)

    if n_args==1:
        config_path = 'config.txt'
    elif n_args==2:
        config_path = sys.argv[1]
    else:
        print("usage: script.py [config_path]")
        sys.exit(1)

    print(f'config file : {config_path}')

    config = load_config(config_path)

    if config is None:
        print("could not load config file")
        print(f"creating sample config file with path '{config_path}'")

        config = {"tg_token":"abcd", "qbt_username":"admin", "qbt_password":"adminadmin", "chat_id":None}
        save_config(config, config_path)
        sys.exit(2)


    updater = Updater(token=config["tg_token"], use_context=True)

    dispatcher:Dispatcher = updater.dispatcher

    import logging
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    #HANDLERS

    def start(update, context):
        context.bot.send_message(chat_id=update.effective_chat.id, text="booba")

    from telegram.ext import CommandHandler

    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)

    GAME_ID = None
    PLAYERS = set()

    def join_handler(update, context):
        global GAME_ID
        if GAME_ID is None:
            return

        if update.effective_message is None or update.effective_message.text is None:
            return

        id = update.effective_message.text.split(' ')
        if len(id)<2:
            return


        try:
            id = int(id[1])
        except ValueError:
            return

        user_id = update.effective_message.from_user
        if user_id is None:
            return
        user_id = user_id.id

        if id!=GAME_ID or user_id in PLAYERS:
            return

        PLAYERS.add(user_id)

        context.bot.send_message(chat_id=update.effective_chat.id, text="ok", reply_markup=make_keyboard())



    join_handler = CommandHandler('join', join_handler)
    dispatcher.add_handler(join_handler)

    def extract_number_argument(s:str):
        parts = s.split(' ', 1)
        print(parts)
        try:
            number_str = parts[1]
            number = int(number_str)
            return number
        except ValueError:
            pass
        except IndexError:
            pass

        return None


    def create_handler(update, context):
        if not check_permissions(update):
            return

        global GAME_ID

        if GAME_ID is not None:
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"game {GAME_ID} in progress")
            return

        GAME_ID = random.randint(1000, 9999)
        PLAYERS.clear()
        context.bot.send_message(chat_id=update.effective_chat.id, text=str(GAME_ID))

    create_handler = CommandHandler('create', create_handler)
    dispatcher.add_handler(create_handler)

    def stop_handler(update, context):
        if not check_permissions(update):
            return
        global GAME_ID
        if GAME_ID is None:
            context.bot.send_message(chat_id=update.effective_chat.id, text="nothing to stop")
            return

        GAME_ID = None
        global PLAYERS
        PLAYERS.clear()
        context.bot.send_message(chat_id=update.effective_chat.id, text="ok")

    dispatcher.add_handler(CommandHandler('stop', stop_handler))

    VOTES = None

    def vote_handler(update, context):
        if not check_permissions(update):
            return

        global VOTES

        if VOTES is not None:
            context.bot.send_message(chat_id=update.effective_chat.id, text="there is vote in progress")
            return

        if GAME_ID is None:
            context.bot.send_message(chat_id=update.effective_chat.id, text="you need to create a game")
            return

        VOTES = {}

        result_id = update.effective_chat.id

        msg = update.effective_message.text

        maybe_argument = extract_number_argument(msg)
        if maybe_argument is None:
            argument = 15
        else:
            argument = maybe_argument

        def compute_results():
            global VOTES
            if VOTES is None:
                msg = "got no votes"
            else:
                positive = 0
                negative = 0
                for k,v in VOTES.items():
                    if v:
                        positive += 1
                    else:
                        negative += 1
                msg = f"positive: {positive}, negative: {negative}"
            context.bot.send_message(result_id, msg)
            VOTES = None

        t = Timer(argument, compute_results)
        t.start()
        context.bot.send_message(result_id, f"vote started for {argument} second(s)")

    dispatcher.add_handler(CommandHandler('vote', vote_handler))

    YES_MARK = "✅"
    NO_MARK = "❌"

    def make_keyboard():
        global YES_MARK
        global NO_MARK
        keyboard = [[KeyboardButton(YES_MARK),
                    KeyboardButton(NO_MARK), ]]
        return ReplyKeyboardMarkup(keyboard)

    def yes_handler(bot, update):
        query = update.callback_query

        # CallbackQueries need to be answered, even if no notification to the user is needed
        # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
        query.answer()
        print("yes")

    def no_handler(bot, update):
        query = update.callback_query

        # CallbackQueries need to be answered, even if no notification to the user is needed
        # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
        query.answer()
        print("no")

    def handle_vote(update, context) -> bool:
        global GAME_ID
        if GAME_ID is None or VOTES is None:
            return False

        if update.effective_message is None or update.effective_message.text is None:
            return False

        user_id = update.effective_message.from_user
        if user_id is None:
            return False
        user_id = user_id.id

        if user_id not in PLAYERS:
            return False

        global YES_MARK, NO_MARK

        mapping = {YES_MARK: True, NO_MARK: False}

        vote = mapping.get(update.effective_message.text)

        print(f"{user_id} voted {vote}")

        if VOTES is not None:
            VOTES[user_id] = vote
            context.bot.send_message(chat_id=update.effective_chat.id, text="ваш голос учтён", reply_markup=make_keyboard())

        return True


    def got_message(update, context):

        check_key(update.effective_message)

        if handle_vote(update, context):
            return

        global YES_MARK, NO_MARK

        if update.effective_message is not None \
            and update.effective_message.text not in (YES_MARK, NO_MARK):
            # do not reply to votes
            context.bot.send_message(chat_id=update.effective_chat.id, text="ладно", reply_markup=make_keyboard())

        if update.channel_post is not None and update.channel_post.text is not None:
            print(f"{update.channel_post.sender_chat.title}: {update.channel_post.text}")

        elif update.message is not None and update.message.text is not None: # message
            print(f"{update.message.from_user.username}: {update.message.text}")


    from telegram.ext import MessageHandler, Filters

    msg_handler = MessageHandler(Filters.text & (~Filters.command), got_message)

    dispatcher.add_handler(msg_handler)

    updater.start_polling()

    CHAT_ID = config["chat_id"]
    AWAIT_SALT = False
    KEY = ''

    def check_permissions(update):
        global config
        return config["chat_id"] is not None and update.effective_chat.id==config["chat_id"]

    def command_verify():
        import random
        base = string.ascii_lowercase+string.digits
        global KEY
        KEY = ''.join(random.choice(base) for _ in range(8))
        global config


        print(f"generated key: {KEY}")
        global AWAIT_SALT

        while True:
            print("press ENTER to continue or type cancel to cancel verification")
            s = input()
            if s.lower()=='cancel':
                print('cancelled verification, set AWAIT_SALT to False')
                AWAIT_SALT = False
                return
            elif s=='':
                AWAIT_SALT = True
                print("set AWAIT_SALT to True")
                print("salt confirmed, now just type key in desired chat")
                return

    def check_key(msg:telegram.Message):

        global AWAIT_SALT

        if not AWAIT_SALT:
            return

        global config

        if msg.text is not None and msg.text==KEY:
            print(f'verified chat: {msg.chat.title or msg.chat.username}')
            config['chat_id'] = msg.chat.id
            print("set AWAIT_SALT to False")
            AWAIT_SALT = False

            global config_path

            save_config(config, config_path)

            print(f"overwritten config file {config_path}")


    def command_say(s:str):
        if CHAT_ID is None:
            warnings.warn("CHAT_ID is not set, provide it with config file or /verify")
        else:
            updater.bot.send_message(chat_id=CHAT_ID, text=s)


    help_msg = """
    
    say to type to saved chat
    
    verify to verify channel
    
    stop to stop the bot
    
    """
    print(help_msg)

    while True:


        s = input()

        if s=="stop":
            break
        if s.startswith("say"):
            command_say(s.split(' ', 1)[-1])

        elif s.startswith("verify"):
            command_verify()
        else:
            print(help_msg)

    updater.stop()
