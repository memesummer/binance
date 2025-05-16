# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2023/12/15 4:10 下午
#    @Description   :
#
# ===============================================================
import csv
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta

import schedule
import telebot
from requests.exceptions import Timeout

from binance_future import format_number, get_funding_rate
from main import get_oid_openInterest_diff_rank, get_oi_increase, get_k_lines_future, map_mc_to_threshold, \
    scan_big_order_spot, scan_big_order_future, symbol1000

binance_his = set()
switch_his = set()
bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')

chat_id = "-1002213443358"

bot.send_message(chat_id, "开始推荐多空密码......")

# 配置
BASE_FILENAME = 'binance_alert'  # 基础文件名
FILE_EXTENSION = '.csv'  # 文件扩展名
MAX_FILE_SIZE = 10 * 1024 * 1024  # 最大文件大小：10MB（可调整）
COLUMNS = ['timestamp', 'time', 'symbol', 'long_short_type', 'count', 'market_str']  # 固定列名
thresholds = {'BTC': 2500000, 'ETH': 1000000, 'SOL': 1000000, 'DOGE': 500000, 'XRP': 500000}
big_record = set()

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))


def get_utc8_time():
    utc8 = timezone(timedelta(hours=8))  # UTC+8 时区
    return int(datetime.now(utc8).timestamp()), datetime.now(utc8).strftime('%Y-%m-%d %H:%M:%S')


# 获取当前有效的文件名
def get_current_filename():
    index = 0
    while True:
        filename = os.path.join(current_dir, f"{BASE_FILENAME}_{index}{FILE_EXTENSION}")
        # 检查文件是否存在及大小
        if not os.path.exists(filename):
            return filename
        if os.path.getsize(filename) < MAX_FILE_SIZE:
            return filename
        index += 1


def remove_symbols(text):
    # 使用正则表达式，保留字母、数字和空格
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    return cleaned_text


def safe_send_message(chat_id, message):
    try:
        bot.send_message(chat_id, message, timeout=10)  # 设置超时时间为10秒
    except Timeout:
        bot.send_message(chat_id, "发送消息超时，正在重试...")
    except Exception as e:
        bot.send_message(chat_id, f"市场增量 消息发送失败: {remove_symbols(message)} 错误：{e}")


def format_price(symbol, price):
    if symbol.startswith("1000") or symbol in symbol1000:
        return price * 1000
    else:
        return price


def get_volume_increase_15(symbol, r=10):
    data15 = get_k_lines_future(symbol, '15m', 2)
    # 再看15min内是否有交易量激增
    v_now = float(data15[1][7])
    v_past = float(data15[0][7])
    v_ratio = round(float(v_now / v_past), 2)
    if v_ratio >= r:
        if data15[1][4] > data15[0][4]:
            v15_list = [1, 1, v_ratio]
        else:
            v15_list = [1, 0, v_ratio]
    else:
        v15_list = [0, 0, v_ratio]
    return v15_list, float(data15[1][4])


def get_symbol_other_index(symbol, is_long):
    res = []

    # 趋势指数
    oi_increase, oi_decrease = get_oi_increase(symbol)
    if oi_increase is None or oi_decrease is None:
        safe_send_message(chat_id, f"{symbol}获取持仓递增数据错误")
        res.append([0, 0])
    else:
        if is_long:
            if oi_increase >= 5:
                res.append([1, oi_increase])
            else:
                res.append([0, oi_increase])
        else:
            if oi_decrease >= 5:
                res.append([1, oi_decrease])
            else:
                res.append([0, oi_decrease])

    # 脉冲指数
    v15_list, price = get_volume_increase_15(symbol)
    if is_long:
        if v15_list[0] == 1 and v15_list[1] == 1:
            res.append([1, v15_list[2]])
        else:
            res.append([0, 0])
    else:
        if v15_list[0] == 1 and v15_list[1] == 0:
            res.append([1, v15_list[2]])
        else:
            res.append([0, 0])

    # 大单扫描
    if symbol[:-4] in thresholds.keys():
        threshold = thresholds[symbol[:-4]]
    else:
        token_info_file_path = os.path.join(current_dir, "token_data.json")
        with open(token_info_file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            market_cap = 0
            for token in data['data']:
                if token['symbol'].lower() == symbol[:-4].lower():
                    market_cap = round(token['quote']['USD']['market_cap'] / 100000000, 2)
                    break
        threshold = map_mc_to_threshold(market_cap)
    buy_spot, sell_spot = scan_big_order_spot(symbol, target=threshold)
    buy_future, sell_future = scan_big_order_future(symbol, target=threshold)
    spot = []
    future = []
    if len(buy_spot) > 0:
        for v in buy_spot:
            if v[1] not in big_record:
                spot.append([1, v[0], v[2], v[1]])
                big_record.add(v[1])
    if len(sell_spot) > 0:
        for v in sell_spot:
            if v[1] not in big_record:
                spot.append([0, v[0], v[2], v[1]])
                big_record.add(v[1])
    if len(buy_future) > 0:
        for v in buy_future:
            if v[1] not in big_record:
                future.append([1, v[0], v[2], v[1]])
                big_record.add(v[1])
    if len(sell_future) > 0:
        for v in sell_future:
            if v[1] not in big_record:
                future.append([0, v[0], v[2], v[1]])
                big_record.add(v[1])
    if len(spot) > 0 or len(future) > 0:
        res.append([1, spot, future])
    else:
        res.append([0, spot, future])
    star_count = sum(1 for sublist in res if sublist and sublist[0] == 1)
    return star_count, res, price


def get_symbol_other_index_str(symbol, ll, is_long):
    res = ""
    a = ll[0]
    if is_long:
        if a[0] == 1:
            res += f"📈趋势增量：`{a[1]}`\n"
        else:
            res += f"📈趋势增量：◻️\n"
    else:
        if a[0] == 1:
            res += f"📉趋势缩量：`{a[1]}`\n"
        else:
            res += f"📉趋势缩量：◻️\n"

    b = ll[1]
    if is_long:
        if b[0] == 1:
            res += f"🔥脉冲指数：`{int(b[1] * 100)}%`\n"
        else:
            res += f"🔥脉冲指数：◻️\n"
    else:
        if b[0] == 1:
            res += f"❄️脉冲指数：`{int(b[1] * 100)}%`\n"
        else:
            res += f"❄️脉冲指数：◻️\n"

    c = ll[2]
    if c[0] == 1:
        spot = c[1]
        future = c[2]
        st = "🔄大单交易：\n"
        if len(spot) > 0:
            for l in spot:
                fn = format_number(l[1])
                price = format_price(symbol, l[2])
                trade_time = l[3]
                utc_timestamp = int(trade_time) // 1000
                utc_plus_8_time = datetime.utcfromtimestamp(utc_timestamp) + timedelta(hours=8)
                time_only = utc_plus_8_time.strftime("%H:%M")
                if l[0] == 0:
                    st += f"- 🟥现货在{time_only}以`{price}`卖出了`{fn}`，达到阈值\n"
                if l[0] == 1:
                    st += f"- 🟩现货在{time_only}以`{price}`买入了`{fn}`，达到阈值\n"
        if len(future) > 0:
            for l in future:
                fn = format_number(l[1])
                price = format_price(symbol, l[2])
                trade_time = l[3]
                utc_timestamp = int(trade_time) // 1000
                utc_plus_8_time = datetime.utcfromtimestamp(utc_timestamp) + timedelta(hours=8)
                time_only = utc_plus_8_time.strftime("%H:%M")
                if l[0] == 0:
                    st += f"- 🟥期货在{time_only}以`{price}`卖出了`{fn}`，达到阈值\n"
                if l[0] == 1:
                    st += f"- 🟩期货在{time_only}以`{price}`买入了`{fn}`，达到阈值\n"
        res += st

    else:
        res += "🔄大单交易：◻️\n"
    return res


def run_task():
    try:
        all_list_d, all_list_a = get_oid_openInterest_diff_rank("5m")
        for l in all_list_d:
            diff_ratio = l[3]
            if diff_ratio >= 2:
                symbol = l[0] + 'USDT'
                p_chg = f"{str(l[1])}%"
                if float(l[4]) == -911:
                    market_str = f"{str(l[3])}%｜◻️"
                else:
                    market_str = f"{str(l[3])}%｜{format_number(float(l[4]))}"
                new_timestamp, push_time = get_utc8_time()

                # 获取当前文件名
                record_file_path = get_current_filename()

                # 检查文件是否存在
                file_exists = os.path.exists(record_file_path)

                # Initialize count
                recent_count = 1
                one_hour_ago = new_timestamp - 3600  # 1 hour ago in seconds

                if file_exists:
                    with open(record_file_path, 'r', newline='', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        header = next(reader, None)  # Skip header
                        all_rows = list(reader)[::-1]
                        for row in all_rows:
                            row_timestamp = int(row[0])
                            if row[2] == symbol and int(row[3]) == 1 and row_timestamp >= one_hour_ago:
                                recent_count = int(row[4]) + 1
                                break

                new_row = [new_timestamp, push_time, symbol, 1, recent_count, market_str]
                # 打开文件以追加模式
                with open(record_file_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    # 如果文件不存在，写入表头
                    if not file_exists:
                        writer.writerow(COLUMNS)
                    # 写入新行
                    writer.writerow(new_row)
                s_count, ll, price = get_symbol_other_index(symbol, True)
                star_count = s_count + recent_count
                if star_count >= 1:
                    fr = get_funding_rate(symbol, decimal=4)[1]
                    sym = symbol[4:-4] if symbol.startswith('1000') else symbol[:-4]
                    other_str = get_symbol_other_index_str(symbol, ll, True)
                    res_str = f"""
🔔*symbol*：`{sym}` 做多信号触发🟢｜{star_count * '🌟'}
💰价格：{price} ｜ {p_chg}
⚖️费率：{fr}%
🧲市场增量强度：`{recent_count}` ｜ {market_str}
{other_str}
--------------------------------
"""
                    safe_send_message(chat_id, res_str)

            else:
                continue

        for l in all_list_a:
            diff_ratio = l[3]
            if diff_ratio <= -2:
                symbol = l[0] + 'USDT'
                p_chg = f"{str(l[1])}%"
                if float(l[4]) == -911:
                    market_str = f"{str(l[3])}%｜◻️"
                else:
                    market_str = f"{str(l[3])}%｜{format_number(float(l[4]))}"
                new_timestamp, push_time = get_utc8_time()

                # 获取当前文件名
                record_file_path = get_current_filename()

                # 检查文件是否存在
                file_exists = os.path.exists(record_file_path)

                # Initialize count
                recent_count = 1
                one_hour_ago = new_timestamp - 3600  # 1 hour ago in seconds

                if file_exists:
                    with open(record_file_path, 'r', newline='', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        header = next(reader, None)  # Skip header
                        all_rows = list(reader)[::-1]
                        for row in all_rows:
                            row_timestamp = int(row[0])
                            if row[2] == symbol and int(row[3]) == 0 and row_timestamp >= one_hour_ago:
                                recent_count = int(row[4]) + 1
                                break

                new_row = [new_timestamp, push_time, symbol, 0, recent_count, market_str]
                # 打开文件以追加模式
                with open(record_file_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    # 如果文件不存在，写入表头
                    if not file_exists:
                        writer.writerow(COLUMNS)
                    # 写入新行
                    writer.writerow(new_row)
                s_count, ll, price = get_symbol_other_index(symbol, False)
                star_count = s_count + recent_count
                if star_count >= 1:
                    fr = get_funding_rate(symbol, decimal=4)[1]
                    sym = symbol[4:-4] if symbol.startswith('1000') else symbol[:-4]
                    other_str = get_symbol_other_index_str(symbol, ll, False)
                    res_str = f"""
🔔*symbol*：`{sym}` 做空信号触发🔴｜{star_count * '🔻'}
💰价格：{price} ｜ {p_chg}
⚖️费率：{fr}%
🧯市场缩量强度：`{recent_count}` ｜ {market_str}
{other_str}
--------------------------------
"""
                    safe_send_message(chat_id, res_str)

            else:
                continue
    except Exception as e:
        safe_send_message(chat_id, f"多空密码获取失败：{e}")


print(f"Task executed at {datetime.now()}")

# 每小时第2分钟启动，并每隔5分钟运行
for minute in range(2, 60, 5):
    schedule.every().hour.at(f":{minute:02d}").do(run_task)

while True:
    schedule.run_pending()
    time.sleep(1)
