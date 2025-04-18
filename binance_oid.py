# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2023/12/15 4:10 下午
#    @Description   :
#
# ===============================================================
import re
import time
from collections import Counter
from datetime import datetime

import schedule
import telebot
from requests.exceptions import Timeout

from binance_future import format_number
from main import get_openInterest_diff_rank, get_long_short_switch_point

binance_his = set()
switch_his = set()
bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')

chat_id = "-1002213443358"

bot.send_message(chat_id, "开始推荐净持仓好币......")


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
        bot.send_message(chat_id, f"recommend 消息发送失败: {remove_symbols(message)}")


def find_repeated_sublists_by_first(array):
    # 收集所有子列表及其全局索引
    sublists = [(sublist[0], sublist, (i, j))
                for i, arr in enumerate(array)
                for j, sublist in enumerate(arr)
                if isinstance(sublist, list) and len(sublist) > 0]

    # 统计子列表第一个元素的出现次数
    first_counts = Counter(first for first, _, _ in sublists)

    # 筛选出现次数 >= 2 的第一个元素
    repeated_firsts = [(first, count) for first, count in first_counts.items() if count >= 2]

    # 构建结果列表
    result = []
    for first, count in repeated_firsts:
        # 找到第一个元素为 first 的子列表及其索引
        matching = [[sublist, idx[0]] for f, sublist, idx in sublists if f == first]
        # 构造输出格式: [First value, Count, [Sublist1, index1], ...]
        result.append([first, count] + matching)

    return result


def run_task():
    net_list, all_list = get_openInterest_diff_rank("15m")
    res = ""
    for l in net_list:
        frozen = ''.join(map(str, l))
        if frozen in binance_his:
            continue
        diff_ratio = l[2]
        if diff_ratio >= 100:
            res += f"🐂🌋*symbol*：`{l[0][4:] if l[0].startswith('1000') else l[0]}`\n主力多头扩张`{format_number(float(l[1]))}`｜`{str(l[2])}%`｜`{str(l[3])}%`\n"
            binance_his.add(''.join(map(str, l)))
        else:
            continue
    for l in all_list:
        frozen = ''.join(map(str, l))
        if frozen in binance_his:
            continue
        diff_ratio = l[5]
        if diff_ratio >= 3:
            res += f"🧲🔼*symbol*：`{l[0][4:] if l[0].startswith('1000') else l[0]}`\n市场增量`{format_number(float(l[4]))}`｜`{str(l[5])}%`｜`{str(l[3])}%`\n"
            binance_his.add(''.join(map(str, l)))
        else:
            continue
    # 定期清理历史记录，避免内存泄漏
    if len(binance_his) > 10000:
        binance_his.clear()
    if res:
        safe_send_message(chat_id, res)

    interval_list = ["15m", "30m", "1h", "2h", "4h"]
    array0 = []
    array1 = []
    for i, interval in enumerate(interval_list):
        switch0, switch1 = get_long_short_switch_point(interval)
        array0.append(switch0)
        array1.append(switch1)
        time.sleep(5)

    switch0_str = ""
    result0 = find_repeated_sublists_by_first(array0)
    for res0 in result0:
        frozen = ''.join(map(str, res0))
        if frozen in switch_his:
            continue
        symbol = res0[0]
        switch0_str += f"🔴🐻*symbol*：`{symbol[4:] if str(symbol).startswith('1000') else symbol}`\n"
        for i in range(2, len(res0)):
            inter = interval_list[res0[i][1]]
            switch0_str += f"近{inter}多转空机会：{int(res0[i][0][1][1])}% | {res0[i][0][2][1]} | {res0[i][0][3]}%\n"
        switch0_str += "\n"
        switch_his.add(frozen)
    if switch0_str:
        safe_send_message(chat_id, switch0_str)

    switch1_str = ""
    result1 = find_repeated_sublists_by_first(array1)
    for res1 in result1:
        frozen = ''.join(map(str, res1))
        if frozen in switch_his:
            continue
        symbol = res1[0]
        switch1_str += f"🟢🐂*symbol*：`{symbol[4:] if str(symbol).startswith('1000') else symbol}`\n"
        for i in range(2, len(res1)):
            inter = interval_list[res1[i][1]]
            switch1_str += f"近{inter}空转多机会：{int(res1[i][0][1][1])}% | {res1[i][0][2][1]} | {res1[i][0][3]}%\n"
        switch1_str += "\n"
        switch_his.add(frozen)
    if switch1_str:
        safe_send_message(chat_id, switch1_str)

    if len(switch_his) > 10000:
        switch_his.clear()


print(f"Task executed at {datetime.now()}")

# 每小时第2分钟启动，并每隔5分钟运行
for minute in range(2, 60, 5):
    schedule.every().hour.at(f":{minute:02d}").do(run_task)

while True:
    schedule.run_pending()
    time.sleep(1)
