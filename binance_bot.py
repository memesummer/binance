import atexit
import json
import os
import threading
import time

import requests
import telebot
from requests.adapters import HTTPAdapter
from requests.exceptions import Timeout
from urllib3.util.retry import Retry

from binance_future import format_number
from binance_future import get_future_pending_order_rank, get_spot_pending_order_rank, get_order_table_buy, \
    get_order_table_sell, get_future_price, get_net_rank_table, get_delta_rank_table, get_symbol_oi_table, \
    get_symbol_nf_table
from main import get_latest_price, get_net_volume_rank_future, get_net_volume_rank_spot, get_openInterest_rank, \
    get_symbol_open_interest, get_symbol_info, token_spot_future_delta, scan_big_order, get_gain_lose_rank, \
    get_symbol_net_future

bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')

binance_his = set()
record = set()
monitor_list = []

chat_id = "-1002213443358"

bot.send_message(chat_id, "开始扫描新币......")


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
def get_symbol_oi(message):
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        symbol_oi = get_symbol_open_interest(symbol)
        res = get_symbol_oi_table(symbol_oi)
        bot.reply_to(message, res, parse_mode='Markdown')
    except Exception as e:
        print(e)
        bot.reply_to(message, "请输入正确的参数格式。示例：/i btc")


@bot.message_handler(commands=['n'])
def get_symbol_net(message):
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        symbol_oi = get_symbol_net_future(symbol)
        res = get_symbol_nf_table(symbol_oi)
        bot.reply_to(message, res, parse_mode='Markdown')
    except Exception as e:
        print(e)
        bot.reply_to(message, "请输入正确的参数格式。示例：/n btc")


@bot.message_handler(commands=['t'])
def get_token_info(message):
    try:
        symbol = message.text.split()[1:][0]
        # 获取当前脚本所在的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        token_info_file_path = os.path.join(current_dir, "token_data.json")

        with open(token_info_file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
        res = get_symbol_info(symbol, data)
        bot.reply_to(message, res, parse_mode='Markdown')
    except Exception as e:
        print(e)
        bot.reply_to(message, "请输入正确的参数格式。示例：/t btc")


@bot.message_handler(commands=['d'])
def get_token_sf_delta(message):
    try:
        spot, future = token_spot_future_delta()
        res = f"`只有现货`：{str(spot)}\n"
        res += f"`只有期货`：{str(future)}\n"
        bot.reply_to(message, res, parse_mode='Markdown')
    except Exception as e:
        print(e)
        bot.reply_to(message, "请输入正确的参数格式。示例：/d")


@bot.message_handler(commands=['ma'])
def add_monitor(message):
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        monitor_list.append(symbol)
        res = f"已开始监控{symbol}的大单交易..."
        safe_send_message(chat_id, res)
    except Exception as e:
        print(e)
        bot.reply_to(message, "请输入正确的参数格式。示例：/ma btc")


@bot.message_handler(commands=['md'])
def delete_monitor(message):
    try:
        param = message.text.split()[1:][0]
        symbol = param.upper() + 'USDT'
        monitor_list.remove(symbol)
        res = f"已取消监控{symbol}的大单交易..."
        safe_send_message(chat_id, res)
    except Exception as e:
        print(e)
        bot.reply_to(message, "请输入正确的参数格式。示例：/md btc")


@bot.message_handler(commands=['mc'])
def check_monitor(message):
    try:
        s = ""
        for symbol in monitor_list:
            s += symbol
            s += ' '
        res = f"目前监控的币有：{s}"
        safe_send_message(chat_id, res)
    except Exception as e:
        print(e)
        bot.reply_to(message, "请输入正确的参数格式。示例：/mc")


@bot.message_handler(commands=['g'])
def gain_lose_rank(message):
    try:
        # 将参数分割成两部分
        param1, param2 = message.text.split()[1:]

        interval = param1
        limit = param2
        res = get_gain_lose_rank(interval, limit)
        bot.reply_to(message, res, parse_mode='Markdown')
    except Exception as e:
        print(e)
        bot.reply_to(message, "请输入正确的参数格式。示例：/g 1w 2")


@atexit.register
def exit_handler():
    # 这个函数将在程序退出时自动执行
    print("Exiting program...")
    bot.stop_polling()


def start_bot():
    while True:
        try:
            bot.session = session
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
        bot.send_message(chat_id, "发送消息超时，正在重试...")
    except Exception as e:
        bot.send_message(chat_id, f"消息发送失败: {str(e)}")


def scan():
    while True:
        try:
            if len(monitor_list) == 0:
                res = scan_big_order(record)
            else:
                res = scan_big_order(record, add=monitor_list)
            message = ""
            for item in res:
                frozen_dict = '；'.join(f"{key}:{','.join(map(str, values[1]))}" for key, values in item.items())
                if frozen_dict in binance_his:
                    continue
                for k, vl in item.items():
                    st = ""
                    spot = vl[1][0]
                    future = vl[1][1]
                    if len(spot) > 0:
                        for l in spot:
                            fn = format_number(l[1])
                            if l[0] == 0:
                                st += f"🟥现货卖出了{fn}，达到阈值\n"
                            if l[0] == 1:
                                st += f"🟩现货买入了{fn}，达到阈值\n"
                    if len(future) > 0:
                        for l in future:
                            fn = format_number(l[1])
                            if l[0] == 0:
                                st += f"🟥期货卖出了{fn}，达到阈值\n"
                            if l[0] == 1:
                                st += f"🟩期货买入了{fn}，达到阈值\n"
                    if not st:
                        continue
                    price = vl[0]
                    message += f"""
*🚧symbol：*`{k}` 🚧 
*💰价格：*`{price}`
{st}
{"-" * 32}
                                                                """
                    if len(message) >= 3000:
                        safe_send_message(chat_id, message)
                        message = ""
                    binance_his.add(frozen_dict)
            if message:
                safe_send_message(chat_id, message)
            # 定期清理历史记录，避免内存泄漏
            if len(binance_his) > 10000:
                binance_his.clear()
            if len(record) > 10000:
                record.clear()
            time.sleep(0.1)
        except Exception as e:
            error_message = f"Error occurred: {str(e)}"
            # safe_send_message(chat_id, error_message)  # 报错时通知管理员
            time.sleep(1)  # 等待一段时间后再继续，避免频繁重启


if __name__ == "__main__":
    # 创建自定义的 session
    session = requests.Session()

    # 增加连接池的大小，并且设置重试机制
    retry_strategy = Retry(
        total=3,  # 最大重试次数
        backoff_factor=1,  # 每次重试间隔的时间倍数
        status_forcelist=[429, 500, 502, 503, 504],  # 针对这些状态码进行重试
    )

    adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retry_strategy)
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
