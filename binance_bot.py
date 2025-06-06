import atexit
import csv
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta
from functools import wraps

import pytz
import requests
import telebot
from requests.adapters import HTTPAdapter
from requests.exceptions import Timeout
from urllib3.util.retry import Retry

from binance_future import format_number, format_price
from binance_future import get_future_pending_order_rank, get_spot_pending_order_rank, get_order_table_buy, \
    get_order_table_sell, get_future_price, get_net_rank_table, get_delta_rank_table, get_symbol_oi_table, \
    get_symbol_nf_table, get_delta_diff_rank_table, get_funding_info_str, get_oi_mc_str, get_funding_rate, \
    get_switch_table, get_oi_increase_rank_table, get_symbol_oi_value_table, get_symbol_net_rank_str, \
    get_klines_history_performance_table
from bithumb import bithumb_alert, to_list_on_bithumb
from main import get_latest_price, get_net_volume_rank_future, get_net_volume_rank_spot, get_openInterest_rank, \
    get_symbol_open_interest, get_symbol_info_str, token_spot_future_delta, scan_big_order, get_gain_lose_rank, \
    get_symbol_net_v, get_openInterest_diff_rank, statistic_coin_time, statistic_time, get_long_short_switch_point, \
    create_token_time_plot, create_all_tokens_time_plot, get_openInterest_increase_rank, get_symbol_open_interest_value, \
    get_symbol_net_rank, symbol1000, get_binance_history_performance
from rootdata import root_data_meta_data
from upbit import to_list_on_upbit, get_upbit_volume
from macd import get_macd_str

# 机器人1
# bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')
# 机器人2
# bot = telebot.TeleBot("8077013417:AAFg0uzWmO3zXyvRJNfJORhK9BJTltFUJa0", parse_mode='Markdown')
# 机器人3
bot = telebot.TeleBot("7727377009:AAGxwVbs65PxqMfwP6ugCcMHxMBDrM2jc2o", parse_mode='Markdown')

AUTHORIZED_USERS = [546797136]  # 替换为实际用户 ID

binance_his = set()
record = set()
monitor_list = []

chat_id_inner = "-1002213443358"
chat_id = "-4654295504"
chat_id_alert = "-4609875695"

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
LOG_CSV_FILE = os.path.join(current_dir, "bot_usage_log.csv")

bot.send_message(chat_id, "开始扫描binance大单......")


# 获取当前时间（北京时间）
def get_current_time():
    utc8 = pytz.timezone('Asia/Shanghai')
    return datetime.now(utc8).strftime('%Y-%m-%d %H:%M:%S')


def log_user_action(user_id, username, command, parameters, status, error_message=None):
    with open(LOG_CSV_FILE, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # 如果文件为空，写入表头
        if csvfile.tell() == 0:
            writer.writerow(['timestamp', 'user_id', 'username', 'command', 'parameters', 'status', 'error_message'])
        # 写入日志
        timestamp = get_current_time()
        writer.writerow([timestamp, user_id, username or 'N/A', command, parameters, status, error_message or 'N/A'])


def remove_symbols(text):
    # 使用正则表达式，保留字母、数字和空格
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    return cleaned_text


# 授权检查装饰器
def restricted(func):
    @wraps(func)
    def wrapper(message):
        user_id = message.from_user.id
        if user_id not in AUTHORIZED_USERS:
            bot.reply_to(message, "抱歉，你没有权限使用此机器人！")
            return
        return func(message)

    return wrapper


@bot.message_handler(commands=['o'])
@restricted
def get_order(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/o'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        # 将参数分割成两部分
        param1, param2 = message.text.split()[1:]

        sym = param1.upper() + 'USDT'
        order_value = int(param2) * 10000

        spot_buy, spot_sell = get_spot_pending_order_rank(sym, order_value)
        if spot_buy is None:
            bot.reply_to(message, "请检查输入的symbol和限额是否正确")
        else:
            future_buy, future_sell = get_future_pending_order_rank(sym, order_value)

            price = get_latest_price(sym)

            if future_buy is None and future_sell is None:
                # 只有现货没有期货
                future_buy = []
                future_sell = []
                future_price = "无期货"
            else:
                future_price = get_future_price(sym)

            res = f"""
💸现货价：{price}  |  💸期货价：{future_price}
"""
            if len(spot_buy) == 0 and len(future_buy) == 0:
                res += """
目前没有高于您给的限额的大买单\n
"""
            else:
                table_buy = get_order_table_buy(spot_buy, future_buy)
                res += table_buy
                res += "\n"
            if len(spot_sell) == 0 and len(future_sell) == 0:
                res += """
目前没有高于您给的限额的大卖单\n
"""
            else:
                table_sell = get_order_table_sell(spot_sell, future_sell)
                res += table_sell
            bot.reply_to(message, res, parse_mode='Markdown')
            log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/o BTC 20")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['nf'])
@restricted
def get_net_future(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/nf'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        # 将参数分割成两部分
        param1, param2 = message.text.split()[1:]

        interval = param1
        reverse = True
        if param2 == 'a':
            reverse = False
        net_list = get_net_volume_rank_future(interval, reverse=reverse)
        res = get_net_rank_table(net_list, interval)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/nf 1h d")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['ns'])
@restricted
def get_net_spot(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/ns'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        # 将参数分割成两部分
        param1, param2 = message.text.split()[1:]

        interval = param1
        reverse = True
        if param2 == 'a':
            reverse = False
        net_list = get_net_volume_rank_spot(interval, reverse=reverse)
        res = get_net_rank_table(net_list, interval)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/ns 1h d")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['oi'])
@restricted
def get_open_interest_rank(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/oi'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        # 将参数分割成两部分
        param1, param2 = message.text.split()[1:]

        interval = param1
        reverse = True
        if param2 == 'a':
            reverse = False
        net_list, all_list = get_openInterest_rank(interval, reverse=reverse)
        res = get_delta_rank_table(net_list, all_list, interval)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/oi 1h d")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['oid'])
@restricted
def get_open_interest_diff_rank(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/oid'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        # 将参数分割成两部分
        param1, param2 = message.text.split()[1:]

        interval = param1
        reverse = True
        if param2 == 'a':
            reverse = False
        net_list, all_list = get_openInterest_diff_rank(interval, reverse=reverse)
        res = get_delta_diff_rank_table(net_list, all_list, interval)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, f"{e}请输入正确的参数格式。示例：/oid 1h d")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['i'])
@restricted
def get_symbol_oi(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/i'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        if symbol in symbol1000:
            symbol = '1000' + symbol
        fr = get_funding_rate(symbol, decimal=4)[1]
        res = f"`费率：{fr}%`\n\n"
        symbol_oi = get_symbol_open_interest(symbol)
        res += get_symbol_oi_table(symbol_oi)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/i btc")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['iv'])
@restricted
def get_symbol_oi_value(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/iv'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        fr = get_funding_rate(symbol, decimal=4)[1]
        res = f"`费率：{fr}%`\n\n"
        symbol_oi = get_symbol_open_interest_value(symbol)
        res += get_symbol_oi_value_table(symbol_oi)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/iv btc")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['r'])
@restricted
def get_symbol_net_volume_rank(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/r'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        param1, param2 = message.text.split()[1:]
        symbol_list = param1.split(',')
        symbol_list = [symbol.upper() + 'USDT' for symbol in symbol_list]
        interval = param2
        res_dict = get_symbol_net_rank(symbol_list, interval)
        res = get_symbol_net_rank_str(res_dict)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/r btc")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['ii'])
@restricted
def get_oi_increase(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/i'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        # 将参数分割成两部分
        interval = message.text.split()[1:][0]
        in_list, de_list = get_openInterest_increase_rank(interval)
        res = get_oi_increase_rank_table(in_list, de_list)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/ii 15m")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['s'])
@restricted
def get_switch(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/s'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        interval = message.text.split()[1:][0]
        switch0, switch1 = get_long_short_switch_point(interval)
        res = get_switch_table(switch0, switch1, interval)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, f"请输入正确的参数格式。示例：/s 1h")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['n'])
@restricted
def get_symbol_net(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/n'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        symbol_oi = get_symbol_net_v(symbol)
        res = get_symbol_nf_table(symbol_oi)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/n btc")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['t'])
@restricted
def get_token_info(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/t'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        symbol = message.text.split()[1:][0]
        # 获取当前脚本所在的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        token_info_file_path = os.path.join(current_dir, "token_data.json")

        with open(token_info_file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
        res = get_symbol_info_str(symbol, data)
        res += "\n"
        res += root_data_meta_data(symbol)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/t btc")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['h'])
@restricted
def get_binance_performance_history(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/h'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        text = message.text.split()
        if len(text) == 1:
            limit = 10
        else:
            limit = int(text[1])
        res_list = get_binance_history_performance(limit)
        res = get_klines_history_performance_table(res_list)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/h 10")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['d'])
@restricted
def get_token_sf_delta(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/d'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        spot, future = token_spot_future_delta()
        res = f"`只有现货`：{str(spot)}\n"
        res += f"`只有期货`：{str(future)}\n"
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/d")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['macd'])
@restricted
def get_token_sf_delta(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/macd'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        res = get_macd_str()
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/d")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['ma'])
@restricted
def add_monitor(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/ma'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        monitor_list.append(symbol)
        res = f"已开始监控{symbol}的大单交易..."
        safe_send_message(chat_id, res)
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/ma btc")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['md'])
@restricted
def delete_monitor(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/md'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        monitor_list.remove(symbol)
        res = f"已取消监控{symbol}的大单交易..."
        safe_send_message(chat_id, res)
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/md btc")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['mc'])
@restricted
def check_monitor(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/mc'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        s = ""
        for symbol in monitor_list:
            s += symbol
            s += ' '
        res = f"目前监控的币有：{s}"
        safe_send_message(chat_id, res)
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/mc")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['g'])
@restricted
def gain_lose_rank(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/g'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        # 将参数分割成两部分
        param1, param2 = message.text.split()[1:]

        interval = param1
        limit = param2
        res = get_gain_lose_rank(interval, limit)
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, f"请输入正确的参数格式。示例：/g 1w 2")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['f'])
@restricted
def funding_rate(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/f'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        st = get_funding_info_str()
        bot.reply_to(message, st, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, f"请输入正确的参数格式。示例：/f")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['om'])
@restricted
def oi_mc_ratio(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/om'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        st = get_oi_mc_str()
        bot.reply_to(message, st, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, f"请输入正确的参数格式。示例：/om")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['stat'])
@restricted
def stat_coin_time(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/stat'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        param = message.text.split()[1:][0]
        if param != 'all':
            symbol = param.upper() + 'USDT'
            res = statistic_coin_time(symbol)
            buf = create_token_time_plot(symbol)
            if not res or not buf:
                bot.reply_to(message, "请输入正确的参数格式。示例：/stat btc", parse_mode='Markdown')
                log_user_action(user_id, username, command, parameters, 'Failed')
            else:
                bot.reply_to(message, res, parse_mode='Markdown')
                bot.send_photo(
                    chat_id=chat_id,
                    photo=buf
                )
                buf.close()
                log_user_action(user_id, username, command, parameters, 'Success')
        elif param == 'all':
            res = statistic_time()
            buf = create_all_tokens_time_plot()
            if not res:
                bot.reply_to(message, "无法获取统计数据", parse_mode='Markdown')
                log_user_action(user_id, username, command, parameters, 'Failed')
            else:
                bot.reply_to(message, res, parse_mode='Markdown')
                if buf:
                    bot.send_photo(
                        chat_id=chat_id,
                        photo=buf
                    )
                    buf.close()
                log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, f"请输入正确的参数格式。示例：/stat btc")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['ul'])
@restricted
def upbit_to_list(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/ul'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        up = to_list_on_upbit()
        res = f"`还没上upbit的潜力币`：{str(up)}\n"
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/ul")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['up'])
@restricted
def up_volume(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/up'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        unit = message.text.split()[1:][0]
        res = get_upbit_volume(unit)
        safe_send_message(chat_id, res)
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/up 60")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['ba'])
@restricted
def thumb_alert(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = 'ba'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        res = bithumb_alert()
        safe_send_message(chat_id, res)
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/ba")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['bl'])
@restricted
def bithumb_to_list(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/bl'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        bit = to_list_on_bithumb()
        res = f"`还没上bithumb的潜力币`：{str(bit)}\n"
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/bl")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@bot.message_handler(commands=['kl'])
@restricted
def korea_to_list(message):
    user_id = message.from_user.id
    username = message.from_user.username
    command = '/kl'
    parameters = ' '.join(message.text.split()[1:]) if len(message.text.split()) > 1 else 'None'
    log_user_action(user_id, username, command, parameters, 'Started')
    try:
        up = to_list_on_upbit()
        bit = to_list_on_bithumb()
        set1 = set(up)
        set2 = set(bit)
        # 计算交集
        intersection = set1 & set2  # 或 set1.intersection(set2)
        # 计算 list1 独有的部分
        only_in_up = set1 - set2  # 或 set1.difference(set2)
        # 计算 list2 独有的部分
        only_in_bit = set2 - set1  # 或 set2.difference(set1)
        res = f"`两个所都没有上的潜力币`：{str(intersection)}\n"
        res += f"`没上upbit但上了bithumb的潜力币`：{str(only_in_up)}\n"
        res += f"`没上bithumb但上了upbit的潜力币`：{str(only_in_bit)}\n"
        bot.reply_to(message, res, parse_mode='Markdown')
        log_user_action(user_id, username, command, parameters, 'Success')
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/kl")
        log_user_action(user_id, username, command, parameters, 'Failed', e)


@atexit.register
def exit_handler():
    # 这个函数将在程序退出时自动执行
    print("Exiting program...")
    bot.stop_polling()


def clear_pending_updates(bot):
    """清理离线时的积压更新"""
    try:
        updates = bot.get_updates()
        if updates:
            last_update_id = updates[-1].update_id
            bot.get_updates(offset=last_update_id + 1)
            print(f"已清理积压更新，最后的 update_id: {last_update_id}")
        else:
            print("没有积压更新需要清理")
    except Exception as e:
        print(f"清理积压更新时出错: {e}")


def start_bot():
    while True:
        try:
            bot.delete_webhook()
            bot.session = session
            clear_pending_updates(bot)
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            print(f"Error occurred: {e}")
            bot.stop_polling()
            time.sleep(5)  # 等待5秒后重新启动
            continue


def safe_send_message(chat_id, message):
    try:
        bot.send_message(chat_id, message, timeout=10)  # 设置超时时间为10秒
    except Timeout:
        bot.send_message(chat_id_alert, "发送消息超时，正在重试...")
    except Exception as e:
        bot.send_message(chat_id_alert, f"scan 消息发送失败: {remove_symbols(message)},error:{e}")


def scan():
    while True:
        try:
            if len(monitor_list) == 0:
                res = scan_big_order(record)
            else:
                res = scan_big_order(record, add=monitor_list)
            for item in res:
                frozen_dict = '；'.join(f"{key}:{','.join(map(str, values))}" for key, values in item.items())
                if frozen_dict in binance_his:
                    continue
                message = ""
                for k, vl in item.items():
                    st = ""
                    spot = vl[0]
                    future = vl[1]
                    if len(spot) > 0:
                        for l in spot:
                            fn = format_number(l[1])
                            price = format_price(k, l[2])
                            trade_time = l[3]
                            utc_timestamp = int(trade_time) // 1000
                            utc_plus_8_time = datetime.utcfromtimestamp(utc_timestamp) + timedelta(hours=8)
                            time_only = utc_plus_8_time.strftime("%H:%M")
                            if l[0] == 0:
                                st += f"🟥现货在{time_only}以`{price}`卖出了`{fn}`，达到阈值\n"
                            if l[0] == 1:
                                st += f"🟩现货在{time_only}以`{price}`买入了`{fn}`，达到阈值\n"
                    if len(future) > 0:
                        for l in future:
                            fn = format_number(l[1])
                            price = format_price(k, l[2])
                            trade_time = l[3]
                            utc_timestamp = int(trade_time) // 1000
                            utc_plus_8_time = datetime.utcfromtimestamp(utc_timestamp) + timedelta(hours=8)
                            time_only = utc_plus_8_time.strftime("%H:%M")
                            if l[0] == 0:
                                st += f"🟥期货在{time_only}以`{price}`卖出了`{fn}`，达到阈值\n"
                            if l[0] == 1:
                                st += f"🟩期货在{time_only}以`{price}`买入了`{fn}`，达到阈值\n"
                    if not st:
                        continue
                    sym = k[4:] if k.startswith("1000") else k
                    message += f"""
*🚧symbol：*`{sym}` 🚧 
{st}
{"-" * 32}
                                                                """
                    safe_send_message(chat_id, message)
                    binance_his.add(frozen_dict)
                    time.sleep(1)
            # 定期清理历史记录，避免内存泄漏
            if len(binance_his) > 50000:
                binance_his.clear()
            if len(record) > 50000:
                record.clear()
            time.sleep(5)
        except Exception as e:
            safe_send_message(chat_id_alert, f"Error in scan thread: {e}")  # 报错时通知管理员
            time.sleep(30)  # 等待一段时间后再继续，避免频繁重启


if __name__ == "__main__":
    # 创建自定义的 session
    session = requests.Session()

    # 增加连接池的大小，并且设置重试机制
    retry_strategy = Retry(
        total=5,  # 最大重试次数
        backoff_factor=2,  # 每次重试间隔的时间倍数
        status_forcelist=[429, 500, 502, 503, 504],  # 针对这些状态码进行重试
    )

    adapter = HTTPAdapter(pool_connections=200, pool_maxsize=200, max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 使用多线程来运行Bot和扫描任务
    bot_thread = threading.Thread(target=start_bot)
    scan_thread = threading.Thread(target=scan)

    # 启动两个线程
    bot_thread.start()
    scan_thread.start()

    # 等待两个线程完成
    bot_thread.join()
    scan_thread.join()
