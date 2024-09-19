# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2024/6/2 16:12
#    @Description   : 
#
# ===============================================================
import time

import telebot
from requests.exceptions import Timeout

from main import scan_big_order

binance_his = set()
record = set()
bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')

chat_id = "-1002213443358"

bot.send_message(chat_id, "开始扫描新币......")


def safe_send_message(chat_id, message):
    try:
        bot.send_message(chat_id, message, timeout=10)  # 设置超时时间为10秒
    except Timeout:
        bot.send_message(chat_id, "发送消息超时，正在重试...")
    except Exception as e:
        bot.send_message(chat_id, f"消息发送失败: {str(e)}")


while True:
    try:
        res = scan_big_order(record)
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
                        if l[0] == 0:
                            st += f"🟥现货卖出了{int(l[1] / 1000)}k，达到阈值\n"
                        if l[0] == 1:
                            st += f"🟩现货买入了{int(l[1] / 1000)}k，达到阈值\n"
                if len(future) > 0:
                    for l in future:
                        if l[0] == 0:
                            st += f"🟥期货卖出了{int(l[1] / 1000)}k，达到阈值\n"
                        if l[0] == 1:
                            st += f"🟩期货买入了{int(l[1] / 1000)}k，达到阈值\n"
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
        safe_send_message(chat_id, error_message)  # 报错时通知管理员
        time.sleep(10)  # 等待一段时间后再继续，避免频繁重启
