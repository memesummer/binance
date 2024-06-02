# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2024/6/2 16:12
#    @Description   : 
#
# ===============================================================
from main import scan_big_order
import telebot
import time

binance_his = set()
bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')

chat_id = "-1002213443358"

bot.send_message(chat_id, "开始扫描新币......")

while True:
    res = scan_big_order()
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
*🚧 symbol：*`{k}`🚧 
*💰价格：*`{price}`
{st}
{"-" * 32}
                                                        """
            binance_his.add(frozen_dict)
    if message:
        bot.send_message(chat_id, message)
    time.sleep(1)
