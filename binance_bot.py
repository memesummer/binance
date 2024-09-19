import atexit
import time

import telebot

from binance_future import get_future_pending_order_rank, get_spot_pending_order_rank, get_order_table_buy, \
    get_order_table_sell, get_future_price, get_net_rank_table, get_delta_rank_table, get_symbol_oi_table
from main import get_latest_price, get_net_volume_rank_future, get_net_volume_rank_spot, get_openInterest_rank, \
    get_symbol_open_interest

bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')


@bot.message_handler(commands=['o'])
def get_order(message):
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
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/o BTC 20")


@bot.message_handler(commands=['nf'])
def get_net_future(message):
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

    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/nf 1h d")


@bot.message_handler(commands=['ns'])
def get_net_spot(message):
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

    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/ns 1h d")


@bot.message_handler(commands=['oi'])
def get_open_interest_rank(message):
    try:
        # 将参数分割成两部分
        param1, param2 = message.text.split()[1:]

        interval = param1
        reverse = True
        if param2 == 'a':
            reverse = False
        net_list = get_openInterest_rank(interval, reverse=reverse)
        res = get_delta_rank_table(net_list, interval)
        bot.reply_to(message, res, parse_mode='Markdown')

    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/oi 1h d")


@bot.message_handler(commands=['i'])
def get_order(message):
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        symbol_oi = get_symbol_open_interest(symbol)
        res = get_symbol_oi_table(symbol_oi)
        bot.reply_to(message, res, parse_mode='Markdown')
    except Exception as e:
        print(e)
        bot.reply_to(message, "请输入正确的参数格式。示例：/i btc")


@atexit.register
def exit_handler():
    # 这个函数将在程序退出时自动执行
    print("Exiting program...")
    bot.stop_polling()


def start_bot():
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            print(f"Error occurred: {e}")
            bot.stop_polling()
            time.sleep(5)  # 等待5秒后重新启动
            continue


start_bot()
