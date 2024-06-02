# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2023/12/15 4:10 下午
#    @Description   : 
#
# ===============================================================
from main import recommend
import telebot
import time
import pandas as pd

binance_his = set()
bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')

# chat_id = "-4020273113"
chat_id = "-1002213443358"
cir_df = pd.read_csv("circulating.txt", sep='\t', header=None, names=['symbol', 'circle_supply'], encoding='utf-8')

bot.send_message(chat_id, "开始推荐新币......")

while True:
    # bot.send_message(chat_id, "这1分钟：")
    res = recommend(cir_df)
    message = ""
    for item in res:
        frozen_dict = '；'.join(f"{key}:{','.join(map(str, values[1]))}" for key, values in item.items())
        if frozen_dict in binance_his:
            continue
        for k, vl in item.items():
            st = ""
            v = vl[1]
            for value in v:
                if value[0] == 1:
                    p_len4 = value[1]
                    v_len4 = value[2]
                    st += f"🟢｜💹4小时价格连续增长：{p_len4}\n"
                    st += f"🟢｜📊4小时交易量连续增长：{v_len4}\n"
                if value[0] == 2:
                    p_len1 = value[1]
                    v_len1 = value[2]
                    st += f"🔵｜💡1小时价格连续增长：{p_len1}\n"
                    st += f"🔵｜ℹ️1小时交易量连续增长：{v_len1}\n"
                if value[0] == 3:
                    st += f"🎯4小时交易量占流通市值比例达到：{round(value[1] * 100, 0)}%\n"
                if value[0] == 4:
                    st += f"🚀近15分钟交易量增长：{round(value[1] * 100, 0)}%\n"
                if value[0] == 5:
                    buy_spot = value[1]
                    buy_future = value[2]
                    index = {0: 10, 1: 50, 2: 100}
                    for i in range(3):
                        if buy_spot[i] == 1:
                            st += f"🔔*[{index[i]}万]*以上的*[现货]*挂单购买力更强\n"
                        if buy_future[i] == 1:
                            st += f"🔔*[{index[i]}万]*以上的*[期货]*挂单购买力更强\n"
                if value[0] == 6:
                    agg_spot = value[1]
                    agg_future = value[2]
                    for vo in agg_spot:
                        vk = int(vo / 1000)
                        st += f"🚨近期*[现货]*有交易额为*{vk}k*的大额订单成交\n"
                    for vo in agg_future:
                        vk = int(vo / 1000)
                        st += f"🚨近期*[期货]*有交易额为*{vk}k*的大额订单成交\n"
            if not st:
                continue
            price = vl[0]
            symbol = k
            star = (2 if len(v) == 2 else 3 if len(v) == 3 else 4 if len(v) == 4 else 5 if len(v) == 5 else 6 if len(
                v) == 6 else 1) * "🌟"
            message += f"""
*💎symbol：*`{symbol}`｜{star}
*💰价格：*`{price}`
{st}
{"-" * 32}
                                                        """
            binance_his.add(frozen_dict)
    if message:
        bot.send_message(chat_id, message)
    time.sleep(60)
