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
from datetime import datetime

import schedule
import telebot
from requests.exceptions import Timeout

from binance_future import format_number
from main import get_openInterest_diff_rank

binance_his = set()
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


def run_task():
    net_list, all_list = get_openInterest_diff_rank("15m")
    res = ""
    for l in net_list:
        frozen = ''.join(map(str, l))
        if frozen in binance_his:
            continue
        diff_ratio = l[2]
        if diff_ratio >= 100:
            res += f"🐂🌋*{l[0][4:] if l[0].startswith('1000') else l[0]}*主力多头扩张`{format_number(float(l[1]))}`｜`{str(l[2])}%`｜`{str(l[3])}%`\n"
            binance_his.add(''.join(map(str, l)))
        else:
            continue
    for l in all_list:
        frozen = ''.join(map(str, l))
        if frozen in binance_his:
            continue
        diff_ratio = l[5]
        if diff_ratio >= 3:
            res += f"🧲🔼*{l[0][4:] if l[0].startswith('1000') else l[0]}*市场增量`{format_number(float(l[4]))}`｜`{str(l[5])}%`｜`{str(l[3])}%`\n"
            binance_his.add(''.join(map(str, l)))
        else:
            continue
    # 定期清理历史记录，避免内存泄漏
    if len(binance_his) > 10000:
        binance_his.clear()
    if res:
        safe_send_message(chat_id, res)


print(f"Task executed at {datetime.now()}")

# 每小时第3分钟启动，并每隔5分钟运行
for minute in range(3, 60, 5):
    schedule.every().hour.at(f":{minute:02d}").do(run_task)

while True:
    schedule.run_pending()
    time.sleep(1)
