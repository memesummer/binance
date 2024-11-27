# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2023/12/15 4:10 下午
#    @Description   : 
#
# ===============================================================
import os
import re
import time

import pandas as pd
import telebot
from requests.exceptions import Timeout

from main import recommend

binance_his = set()
bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')

# chat_id = "-4020273113"
chat_id = "-1002213443358"

# 获取当前脚本所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 构建 circulating.txt 的绝对路径
file_path = os.path.join(current_dir, "circulating.txt")
cir_df = pd.read_csv(file_path, sep='\t', header=None, names=['symbol', 'circle_supply'], encoding='utf-8')

bot.send_message(chat_id, "开始推荐新币......")


def remove_symbols(text):
    # 使用正则表达式，保留字母、数字和空格
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    return cleaned_text


def safe_send_message(chat_id, message):
    try:
        bot.send_message(chat_id, remove_symbols(message), timeout=10)  # 设置超时时间为10秒
    except Timeout:
        bot.send_message(chat_id, "发送消息超时，正在重试...")
    except Exception as e:
        bot.send_message(chat_id, f"recommend 消息发送失败: {remove_symbols(str(e))}")


while True:
    try:
        res = recommend(cir_df)
        # 按照 flag 列表长度降序排序
        sorted_res = sorted(res, key=lambda item: len(list(item.values())[0][1]), reverse=True)

        message = ""
        for item in sorted_res:
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
                    if value[0] == 8:
                        longshortRatio_rate4 = round(value[1] * 100, 0)
                        st += f"⬆️近*1h合约*主动买卖比显著增加🔺{longshortRatio_rate4}%\n"
                    if value[0] == 7:
                        longshortRatio_rate1 = round(value[1] * 100, 0)
                        st += f"⬆️近*30min合约*主动买卖比显著增加🔺{longshortRatio_rate1}%\n"
                    if value[0] == 9:
                        taker_ratio4 = round(value[1] * 100, 0)
                        st += f"💪近*4小时现货*主动买入量占比较高🥧：{taker_ratio4}%\n"
                    if value[0] == 10:
                        taker_ratio1 = round(value[1] * 100, 0)
                        st += f"💪近*1小时现货*主动买入量占比较高🥧：{taker_ratio1}%\n"
                    if value[0] == 11:
                        t_len4 = value[1]
                        st += f"💪📈近*4小时现货*主动买入占比连续增长：{t_len4}\n"
                    if value[0] == 12:
                        t_len1 = value[1]
                        st += f"💪📈近*1小时现货*主动买入占比连续增长：{t_len1}\n"
                if not st:
                    continue
                price = vl[0]
                symbol = k
                star = len(v) * "🌟"
                message += f"""
*💎symbol：*`{symbol}`｜{star}
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

        time.sleep(60)
    except Exception as e:
        error_message = f"Error occurred: {str(e)}"
        safe_send_message(chat_id, error_message)  # 报错时通知管理员
        time.sleep(10)  # 等待一段时间后再继续，避免频繁重启
