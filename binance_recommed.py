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
from binance_future import format_number

binance_his = set()
bot = telebot.TeleBot("6798857946:AAEVjD81AKrCET317yb-xNO1-DyP3RAdRH0", parse_mode='Markdown')

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
        bot.send_message(chat_id, message, timeout=10)  # 设置超时时间为10秒
    except Timeout:
        bot.send_message(chat_id, "发送消息超时，正在重试...")
    except Exception as e:
        bot.send_message(chat_id, f"recommend 消息发送失败: {remove_symbols(message)}")


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
                        st += f"🟢💹趋势引擎：{p_len4}\n"
                        st += f"🟢📊趋势动能：{v_len4}\n"
                    if value[0] == 2:
                        p_len1 = value[1]
                        v_len1 = value[2]
                        st += f"🔵｜💡1小时价格连续增长：{p_len1}\n"
                        st += f"🔵｜ℹ️1小时交易量连续增长：{v_len1}\n"
                    if value[0] == 3:
                        st += f"🎯🌊资金潮汐率：{int(value[1] * 100)}%\n"
                    if value[0] == 4:
                        st += f"🚀🔥脉冲指数：`{int(value[1] * 100)}%`\n"
                    if value[0] == 5:
                        buy_spot = value[1]
                        buy_future = value[2]
                        index = {0: "小单", 1: "中单", 2: "大单", 3: "超大单"}
                        for i in range(4):
                            if buy_spot[i] == 1:
                                st += f"🔔[{index[i]}][现货]潜在购买力突出，存在托盘\n"
                            if buy_future[i] == 1:
                                st += f"🔔[{index[i]}][期货]潜在购买力突出，存在托盘\n"
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
                        st += f"🧿️主动狩猎比：{taker_ratio4}%\n"
                    if value[0] == 10:
                        taker_ratio1 = round(value[1] * 100, 0)
                        st += f"💪近*1小时现货*主动买入量占比较高🥧：{taker_ratio1}%\n"
                    if value[0] == 11:
                        t_len4 = value[1]
                        st += f"⚔️主动狩猎指数：{t_len4}\n"
                    if value[0] == 12:
                        t_len1 = value[1]
                        st += f"💪📈近*1小时现货*主动买入占比连续增长：{t_len1}\n"
                    if value[0] == 13:
                        om_list = value[1]
                        oi = om_list[0]
                        mc = om_list[1]
                        om_ratio = om_list[2]
                        st += f"🏦🕹️控盘强度：{int(oi / mc * 100)}%\n"
                    if value[0] == 14:
                        st += f"🐂🌋主力多头扩张{format_number(float(value[1]))}｜{str(value[2])}%\n"
                    if value[0] == 15:
                        st += f"🧲🔼市场增量{format_number(float(value[1]))}｜{str(value[2])}%\n"
                    if value[0] == 16:
                        st += f"🧩🧬多维健康度：{value[1]}/20\n"
                    if value[0] == 17:
                        st += f"🧩🧑‍🤝‍🧑多维活跃度：{value[1]}/20\n"
                    if value[0] == 18:
                        st += f"🧩🚀多维脉冲指数：`{int(value[1] * 100)}%`\n"
                    if value[0] == 19:
                        for i in value[1]:
                            st += f"🧩🚨多维警报：{i}\n"
                if not st:
                    continue
                price = vl[0]
                symbol = k
                star = len(v) * "🌟"
                message += f"""
*💎symbol：*`{symbol}`｜{star}
💰价格：{price}
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

        time.sleep(90)
    except Exception as e:
        error_message = f"Error occurred: {str(e)}"
        safe_send_message(chat_id, error_message)  # 报错时通知管理员
        time.sleep(10)  # 等待一段时间后再继续，避免频繁重启
