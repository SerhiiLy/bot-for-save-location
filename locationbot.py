import os

from collections import defaultdict

import telebot

import redis
from telebot import types
token = '1239132956:AAHEQwQ5_HxYi5MhHSGpHaIC_LOMYCd0bUQ'

bot = telebot.TeleBot(token)

redis_url = os.getenv('REDIS_URL', 'redis://h:p28f165da398e4b03eecb12330946fdae9d3556576beac98003a90014ffb7655e@ec2-52-213-23-142.eu-west-1.compute.amazonaws.com:24909')

# r = redis.Redis(
#     host='localhost',
#     port=6379,
#     db=0,
#     decode_responses=True
# )

r = redis.from_url(redis_url, db=0, decode_responses=True)

START, ADD_NAME, ADD_LOCATION, CONFIRMATION = range(4)

USER_STATE = defaultdict(lambda: START)

keyboard1 = telebot.types.ReplyKeyboardMarkup(True)
btn_add = types.InlineKeyboardButton(text='/add')
btn_list = types.KeyboardButton(text='/list')
btn_reset = types.KeyboardButton(text='/reset')
keyboard1.add(btn_add, btn_list, btn_reset)

def get_state(message):
    return USER_STATE[message.chat.id]


def update_state(message, state):
    USER_STATE[message.chat.id] = state


def write_title_to_redis(message):
    user_id = message.chat.id
    location_title = message.text
    r.lpush(user_id, location_title)


def write_coords_to_redis(user_id, location):
    lat, lon = location.latitude, location.longitude
    title = r.lpop(user_id)
    full_location_data = f'{title}&#124;{lat}&#124;{lon}'
    r.lpush(user_id, full_location_data)


def delete_location(user_id):
    r.lpop(user_id)

# def create_keyboard():
#     keyboard = types.InlineKeyboardMarkup(row_width=2)
#     buttons = [
#         types.InlineKeyboardButton(text=c, callback_data=c)
#         for c in currencies
#     ]
#     keyboard.add(*buttons)
#     return keyboard

@bot.message_handler(
    func=lambda message: get_state(message) == START, commands=['add']
)
def handle_title(message):
    bot.send_message(chat_id=message.chat.id, text='Введите адрес')
    update_state(message, ADD_NAME)

@bot.message_handler(
    func=lambda message: get_state(message) == ADD_NAME)
def handle_location(message):
    if message.text in ('/add', '/list', '/reset'):
        bot.send_message(chat_id=message.chat.id, text='Добавление прервано')
        update_state(message, START)
    else:
        write_title_to_redis(message)
        bot.send_message(chat_id=message.chat.id, text='Отправь локацию')
        update_state(message, ADD_LOCATION)


@bot.message_handler(
    func=lambda message: get_state(message) == ADD_LOCATION,
    content_types=['location']
)
def handle_confirmation(message):
    keyboard2 = telebot.types.ReplyKeyboardMarkup(True, True)
    btn_yes = types.InlineKeyboardButton(text='Да')
    btn_no = types.InlineKeyboardButton(text='Нет')
    keyboard2.add(btn_yes, btn_no)
    bot.send_message(chat_id=message.chat.id, text='Добавить?', reply_markup=keyboard2)
    update_state(message, CONFIRMATION)
    write_coords_to_redis(message.chat.id, message.location)


@bot.message_handler(func=lambda message: get_state(message) == CONFIRMATION)
def handle_finish(message):
    if message.text in ('/add', '/list', '/reset'):
        update_state(message, START)
        delete_location(message.chat.id)
        bot.send_message(chat_id=message.chat.id, text='Добавление прервано')
    else:
        if 'да' in message.text.lower():
            bot.send_message(
                chat_id=message.chat.id,
                text=f'Локация добавлена',
                reply_markup=keyboard1
            )
            update_state(message, START)
        if 'нет' in message.text.lower():
            bot.send_message(
                chat_id=message.chat.id,
                text=f'Локация не добавлена', 
                reply_markup=keyboard1
            )
            update_state(message, START)
            delete_location(message.chat.id)


@bot.message_handler(
    func=lambda x: True, commands=['list']
)
def handle_list(message):
    if get_state(message) != START:
        update_state(message, START)
        r.lpop(message.chat.id)
    else:
        last_locations = r.lrange(message.chat.id, 0, 10)
        if last_locations:
            bot.send_message(chat_id=message.chat.id, text='Последние локации:')

            for location in last_locations:
                if '&#124;' in location:
                    title, lat, lon = location.split('&#124;')
                    bot.send_message(chat_id=message.chat.id, text=title)
                    bot.send_location(message.chat.id, lat, lon)
                else:
                    bot.send_message(chat_id=message.chat.id, text=location)
        else:
            bot.send_message(chat_id=message.chat.id, text='Нету сохранених локаций')


@bot.message_handler(func=lambda x: True, commands=['reset'])
def handle_confirmation(message):
    r.flushdb()
    bot.send_message(chat_id=message.chat.id, text='Все локации удалены')


@bot.message_handler(func=lambda x: True, commands=['start'])
def handle_confirmation(message):
   
    bot.send_message(chat_id=message.chat.id, text='Введите команду /add для добавления локации')
    bot.send_message(chat_id=message.chat.id,
                     text='Введите команду /list для просмотра 10 последних локаций')
    bot.send_message(chat_id=message.chat.id,
                     text='Введите команду /reset для удаления всех локаций', reply_markup=keyboard1)


bot.polling()
