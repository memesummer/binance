import csv
import glob
import io
import json
import os
import re
import threading
import time
from datetime import datetime, timezone, timedelta
from functools import wraps
from itertools import islice

import matplotlib.pyplot as plt
import pandas as pd
import requests
import telebot
from requests.adapters import HTTPAdapter
from requests.exceptions import Timeout
from urllib3.util.retry import Retry

sol_id = 1399811149
# 5万次 (ettoro)
define1 = "1d1cfa84305b78b1ab8cd4205a45f77b231f9686"
# 5万次 （aozone）
define2 = "eab19d30e8cb0d3c39e949aac2dd38ca19da87dc"
# 1万次（mountain）
define3 = "91a19d3b319a0c6642e96c679542e96adc324e09"

sol_sniffer_api_key_list = ['i2e0pwyjlztqemeok2sa6uc2vrk798', 'zkm1hkgigkrwgpvfdximp7qaoqylkk',
                            '6iu82h8hbz9axilnazunu2oyad8mfl', 'aau5mqrwpn9a0ykj8bmwgxo6ywwwr3',
                            "ouwnjyt0ckpornm1ojj4tkl9rhiry6", "vf6vigj6jcudx7s30766sandlyewen",
                            "s0itn9yxyx2b2d2vxt2k4i2ojpjw25", "3of090m7s3y9lvlmhr8kdterdhgewv"]
# probabilities = [0.2, 0.2, 0.2, 0.2, 0.2]

exclude_tokens = [f"So11111111111111111111111111111111111111112:{sol_id}",
                  f"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v:{sol_id}",
                  f"Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB:{sol_id}"]
exclude_tokens_str = json.dumps(exclude_tokens)

url = "https://graph.defined.fi/graphql"

headers1 = {
    "content_type": "application/json",
    "Authorization": define1
}
headers2 = {
    "content_type": "application/json",
    "Authorization": define2
}
headers3 = {
    "content_type": "application/json",
    "Authorization": define3
}
AUTHORIZED_USERS = [546797136, 6808760378, 6672213739, 7205595566]  # 替换为实际用户 ID

bot = telebot.TeleBot("8112245267:AAFedRwTwOz06mVqQ6lqRrnwzuvCLRuLFCg", parse_mode='Markdown')

chat_id = "-4629100773"
chat_id_alert = "-4609875695"
chat_id_inner = "-1002213443358"

bot.send_message(chat_id, "开始推荐sol链MEME币......")

# 配置
BASE_FILENAME = 'sol_push_record'  # 基础文件名
FILE_EXTENSION = '.csv'  # 文件扩展名
MAX_FILE_SIZE = 10 * 1024 * 1024  # 最大文件大小：10MB（可调整）
COLUMNS = ['timestamp', 'time', 'type', 'ca', 'symbol', 'name', 'liq', 'mc', 'price', 'age', 'score', 'count']  # 固定列名

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))


# 获取当前有效的文件名
def get_current_filename():
    index = 0
    while True:
        # 构造文件名：sol_push_record_0.csv, sol_push_record_1.csv, ...
        filename = os.path.join(current_dir, f"{BASE_FILENAME}_{index}{FILE_EXTENSION}")
        # 检查文件是否存在及大小
        if not os.path.exists(filename):
            return filename
        if os.path.getsize(filename) < MAX_FILE_SIZE:
            return filename
        index += 1


def get_utc8_time():
    utc8 = timezone(timedelta(hours=8))  # UTC+8 时区
    return int(datetime.now(utc8).timestamp()), datetime.now(utc8).strftime('%Y-%m-%d %H:%M:%S')


# 统计 ca 列（c 列）在所有文件中出现的次数
def count_ca_occurrences(ca_value):
    count = 0
    # 遍历所有 sol_push_record_*.csv 文件
    for file in glob.glob(os.path.join(current_dir, f"{BASE_FILENAME}_*{FILE_EXTENSION}")):
        try:
            df = pd.read_csv(file)
            # 确保 ca 列存在
            if 'ca' in df.columns:
                count += (df['ca'].astype(str) == str(ca_value)).sum()
        except (pd.errors.EmptyDataError, KeyError):
            continue  # 跳过空文件或无效文件
    return count


# 授权检查装饰器
def restricted(func):
    @wraps(func)
    def wrapper(message):
        user_id = message.from_user.id
        if user_id not in AUTHORIZED_USERS:
            bot.reply_to(message, "抱歉，你没有权限使用此机器人！")
            return
        return func(message)

    return wrapper


def get_if_str(flag):
    if flag:
        return "✅"
    else:
        return "❌"


def get_safe_str(des):
    if des == "high":
        return "🔴-- 高风险：\n"
    elif des == "moderate":
        return "🟡-- 中风险：\n"
    elif des == "low":
        return "🔵-- 低风险：\n"
    elif des == "specific":
        return "🟣-- 特殊风险：\n"
    elif des == "Mintable risks found":
        return " ｜-- Mint权限未丢弃\n"
    elif des == "Freeze risks found":
        return " ｜-- 冻结权限未丢弃\n"
    elif des == "A private wallet owns a significant share of the supply":
        return " ｜-- 个人持有巨额代币\n"
    elif des == "Tokens auto-freeze risks found":
        return " ｜-- 代币自动冻结风险\n"
    elif des == "Significant ownership by top 10 wallets":
        return " ｜-- 前10地址占比过高\n"
    elif des == "Significant ownership by top 20 wallets":
        return " ｜-- 前20地址占比过高\n"
    elif des == "Permanent control risks found":
        return " ｜-- 永久控制风险\n"
    elif des == "Presence of token metadata":
        return " ｜-- 缺乏代币元数据\n"
    elif des == "High locked supply risks found":
        return " ｜-- 池子未锁定\n"
    elif des == "Sufficient liquidity detected":
        return " ｜-- 池子过大\n"
    elif des == "Very low liquidity":
        return " ｜-- 池子过小\n"
    elif des == "Token metadata are immutable":
        return " ｜-- 代币元数据可篡改\n"
    elif des == "Token operates without custom fees":
        return " ｜-- 手续费可篡改\n"
    elif des == "Token has recent user activity":
        return " ｜-- 代币近期有用户行为\n"
    elif des == "Unknown liquidity pools":
        return " ｜-- 未知流动性池\n"
    elif des == "Low count of LP providers":
        return " ｜-- 池子数量过少\n"
    elif des == "Contract was not recently deployed":
        return " ｜-- 合约不是最近部署\n"
    elif des == "Recent interaction within the last 30 days":
        return " ｜-- 近期交互超过30天\n"
    else:
        return "未找到匹配风险"


def get_sol_sniffer_data(ca):
    try:
        for index, api_key in enumerate(sol_sniffer_api_key_list):
            url = f'https://solsniffer.com/api/v2/token/{ca}'

            # api_key = random.choices(sol_sniffer_api_key_list, probabilities)[0]

            # 设置请求头，包含API密钥
            headers = {
                'accept': 'application/json',
                'X-API-KEY': api_key  # 注意：如果API需要在请求头中发送API密钥
            }

            # 发送GET请求
            response = requests.get(url, headers=headers)

            # 检查响应状态码
            if response.status_code == 200:
                # 如果请求成功，打印JSON响应
                res = response.json()['tokenData']

                risk_str = "⚠️风险提示：\n"
                indicator = res['indicatorData']
                for k, v in indicator.items():
                    if v['count'] > 0:
                        risk_str += get_safe_str(k)
                        details = json.loads(v['details'].replace("'", '"'))
                        for m, n in details.items():
                            if n is False:
                                risk_str += get_safe_str(m)
                if risk_str == "⚠️风险提示：\n":
                    risk_str = "⚠️风险提示：无🎉\n"

                ownersList = res['ownersList']
                top10 = 0
                top5 = []
                for i, holder in enumerate(ownersList[:10]):
                    top10 += float(holder['percentage'])
                    if i < 5:
                        top5.append(float(holder['percentage']))
                top10 = int(round(top10, 0))
                t5 = ""
                for k in top5:
                    t5 += f"| {k} "
                top_str = f"👥Top10占比:{top10}% {t5}\n"

                safe_score_str = f"🛡️安全评分：{res['score']}\n"
                audit = res['auditRisk']
                audit_str = f"🔍丢权限{get_if_str(audit['mintDisabled'])}烧池子{get_if_str(audit['lpBurned'])}无冻结权限{get_if_str(audit['freezeDisabled'])}Top10{get_if_str(audit['top10Holders'])}\n"

                final_str = safe_score_str + top_str + audit_str + risk_str
                return final_str
            elif response.status_code == 429:
                if index == len(sol_sniffer_api_key_list) - 1:
                    safe_send_message(chat_id_alert, f"sol sniffer api credits全部用完了")
                    return None
                else:
                    continue
            else:
                # 如果请求失败，打印错误信息
                print(f"Request failed with status code {response.status_code}")
                print(response.text)
    except Exception as e:
        safe_send_message(chat_id_alert, f"safe sniffer api调取有问题：{e}")
        return None


def get_sol_sniffer_datas(new_list):
    try:
        for index, api_key in enumerate(sol_sniffer_api_key_list):
            ca_list = [i['ca'] for i in new_list]
            url = f'https://solsniffer.com/api/v2/tokens'
            # api_key = random.choices(sol_sniffer_api_key_list, probabilities)[0]

            # 设置请求头，包含API密钥
            headers = {
                'accept': 'application/json',
                'X-API-KEY': api_key  # 注意：如果API需要在请求头中发送API密钥
            }
            request_body = {
                "addresses": ca_list
            }

            # 发送GET请求
            response = requests.post(url, headers=headers, json=request_body)

            if response.status_code == 200:

                multi_res = {}
                # 如果请求成功，打印JSON响应
                result = response.json()['data']

                for r in result:
                    key = r['address']
                    res = r['tokenData']

                    risk_str = "⚠️风险提示：\n"
                    indicator = res['indicatorData']
                    for k, v in indicator.items():
                        if v['count'] > 0:
                            risk_str += get_safe_str(k)
                            details = json.loads(v['details'].replace("'", '"'))
                            for m, n in details.items():
                                if n is False:
                                    risk_str += get_safe_str(m)
                    if risk_str == "⚠️风险提示：\n":
                        risk_str = "⚠️风险提示：无🎉\n"

                    # ownersList = res['ownersList']
                    # top10 = 0
                    # top5 = []
                    # for i, holder in enumerate(ownersList[:10]):
                    #     top10 += float(holder['percentage'])
                    #     if i < 5:
                    #         top5.append(float(holder['percentage']))
                    # top10 = int(round(top10, 0))
                    # t5 = ""
                    # for k in top5:
                    #     t5 += f"|{k}"
                    # top = f"Top10占比:{top10}% {t5}\n"

                    safe_score_str = f"🛡️安全评分：{res['score']}\n"
                    audit = res['auditRisk']
                    audit_str = f"🔍丢权限{get_if_str(audit['mintDisabled'])}烧池子{get_if_str(audit['lpBurned'])}无冻结权限{get_if_str(audit['freezeDisabled'])}Top10{get_if_str(audit['top10Holders'])}\n"

                    final_str = safe_score_str + audit_str + risk_str
                    multi_res.update({key: final_str})

                return multi_res
            elif response.status_code == 429:
                if index == len(sol_sniffer_api_key_list) - 1:
                    safe_send_message(chat_id_alert, f"sol sniffer api credits全部用完了")
                    return None
                else:
                    continue
            else:
                # 如果请求失败，打印错误信息
                p = f"Request failed with status code {response.status_code}"
                safe_send_message(chat_id_alert, p + "/" + response.text)
    except Exception as e:
        safe_send_message(chat_id_alert, f"sol sniffer error:{e}")
        return None


def format_number(num, is_int=False):
    if not is_int:
        if abs(num) >= 1000000:
            return f"{(num / 1000000):.1f}M"
        elif abs(num) >= 1000:
            return f"{(num / 1000):.1f}K"
        else:
            return str(round(num, 1))
    else:
        if abs(num) >= 1000000:
            return f"{int(num / 1000000)}M"
        elif abs(num) >= 1000:
            return f"{int(num / 1000)}K"
        else:
            return str(int(num))


def remove_symbols(text):
    # 使用正则表达式，保留字母、数字和空格
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    return cleaned_text


def safe_send_message(chat_id, message):
    try:
        bot.send_message(chat_id, message, parse_mode='Markdown',
                         disable_web_page_preview=True, timeout=10)  # 设置超时时间为10秒
    except Timeout:
        bot.send_message(chat_id_alert, "发送消息超时，正在重试...")
    except Exception as e:
        bot.send_message(chat_id_alert, f"消息发送失败: {remove_symbols(message)},原因：{e}")


def get_top_token(limit, interval, is_volume_based=False, network_id=sol_id):
    try:
        attribute = f"trendingScore{interval}" if not is_volume_based else f"volume{interval}"
        getTopToken = f"""query {{
          filterTokens(
            filters: {{ 
              network: {network_id},
              potentialScam: false,
              launchpadCompleted: true,
              liquidity: {{ gt: 10000 }}
            }},
            rankings: {{ attribute: {attribute}, direction: DESC }},
            limit: {limit},
            excludeTokens: {exclude_tokens_str}
          ) {{
            results {{
                token{{
                    address
                    symbol
                    name
                }}
                volume{interval}
                liquidity
                marketCap
                txnCount{interval}
                change{interval}
                uniqueBuys{interval}
                uniqueSells{interval}
            }}
          }}
        }}"""
        response = requests.post(url, headers=headers2, json={"query": getTopToken})
        res = json.loads(response.text)
        res_list = res['data']['filterTokens']['results']
        return res_list
    except BaseException as e:
        print(e)


def get_rank_buyCount(limit, interval, network_id=sol_id):
    try:
        attribute = f"[{{attribute: txnCount{interval}, direction: DESC}},{{attribute: buyCount{interval}, direction: DESC}}]"
        getTopToken = f"""query {{
          filterTokens(
            filters: {{ 
              network: {network_id},
              potentialScam: false,
              launchpadCompleted: true,
              liquidity: {{ gt: 10000 }}
            }},
            rankings: {attribute},
            limit: {limit},
            excludeTokens: {exclude_tokens_str}
          ) {{
            results {{
                token{{
                    address
                    symbol
                    name
                }}
                volume{interval}
                liquidity
                marketCap
                txnCount{interval}
                buyCount{interval}
                sellCount{interval}
                change{interval}
            }}
          }}
        }}"""
        response = requests.post(url, headers=headers1, json={"query": getTopToken})
        res = json.loads(response.text)
        res_list = res['data']['filterTokens']['results']
        return res_list
    except BaseException as e:
        print(e)


def get_rank_pc(limit, interval, network_id=sol_id):
    try:
        attribute = f"{{attribute: change{interval}, direction: DESC}}"
        getTopToken = f"""query {{
          filterTokens(
            filters: {{ 
              network: {network_id},
              potentialScam: false,
              launchpadCompleted: true,
              liquidity: {{ gt: 10000 }}
            }},
            rankings: {attribute},
            limit: {limit},
            excludeTokens: {exclude_tokens_str}
          ) {{
            results {{
                token{{
                    address
                    symbol
                    name
                }}
                volume{interval}
                liquidity
                marketCap
                change{interval}
            }}
          }}
        }}"""
        response = requests.post(url, headers=headers1, json={"query": getTopToken})
        res = json.loads(response.text)
        res_list = res['data']['filterTokens']['results']
        return res_list
    except BaseException as e:
        print(e)


def get_rank_vc(limit, interval, network_id=sol_id):
    try:
        attribute = f"{{attribute: volumeChange{interval}, direction: DESC}}"
        getTopToken = f"""query {{
          filterTokens(
            filters: {{ 
              network: {network_id},
              potentialScam: false,
              launchpadCompleted: true,
              liquidity: {{ gt: 10000 }}
              change5m: {{ gt: 0.01 }}
              change1: {{ gt: 0.01 }}
              change4: {{ gt: 0.01 }}
              change12: {{ gt: 0.01 }}
              change24: {{ gt: 0.01 }}
              volumeChange5m: {{ gt: 100 }}
              volumeChange1: {{ gt: 0 }}
            }},
            rankings: {attribute},
            limit: {limit},
            excludeTokens: {exclude_tokens_str}
          ) {{
            results {{
                token{{
                    address
                    symbol
                    name
                }}
                volume{interval}
                liquidity
                marketCap
                volumeChange{interval}
                change{interval}
                createdAt
                priceUSD
            }}
          }}
        }}"""
        response = requests.post(url, headers=headers1, json={"query": getTopToken})
        res = json.loads(response.text)
        res_list = res['data']['filterTokens']['results']
        return res_list
    except BaseException as e:
        print(e)


def get_rank_holder(limit, interval, network_id=sol_id):
    try:
        attribute = f"[{{attribute: holders, direction: DESC}},{{attribute: notableHolderCount, direction: DESC}}]"
        getTopToken = f"""query {{
          filterTokens(
            filters: {{ 
              network: {network_id},
              potentialScam: false,
              launchpadCompleted: true,
              liquidity: {{ gt: 10000 }}
            }},
            rankings: {attribute},
            limit: {limit},
            excludeTokens: {exclude_tokens_str}
          ) {{
            results {{
                token{{
                    address
                    symbol
                    name
                }}
                volume{interval}
                liquidity
                marketCap
                txnCount{interval}
                holders
                change{interval}
            }}
          }}
        }}"""
        response = requests.post(url, headers=headers1, json={"query": getTopToken})
        res = json.loads(response.text)
        res_list = res['data']['filterTokens']['results']
        return res_list
    except BaseException as e:
        print(e)


def get_newest_token(limit, interval='5m', network_id=sol_id):
    try:
        attribute = f"createdAt"
        getNewToken = f"""query {{
          filterTokens(
            filters: {{ network: {network_id},
                        potentialScam: false,
                        launchpadCompleted: true
                        }},
            rankings: {{ attribute: {attribute}, direction: DESC }},
            limit: {limit},
            excludeTokens: {exclude_tokens_str}
          ) {{
            results {{
                token{{
                    address
                    symbol
                    name
                }}
                volume{interval}
                liquidity
                txnCount{interval}
                change{interval}
                uniqueBuys{interval}
                uniqueSells{interval}
            }}
          }}
        }}"""
        response = requests.post(url, headers=headers2, json={"query": getNewToken})
        res = json.loads(response.text)
        res_list = res['data']['filterTokens']['results']
        return res_list
    except BaseException as e:
        print(e)


def return_top_token(interval, top_token_list, is_volume_based):
    inter = interval if interval == '5m' else interval + "h"
    res = f"🔥*{inter} trending tokens：*\n" if not is_volume_based else f"🚀*{inter} high volume tokens：*\n"
    res += f"| Token | 池子 | 市值 | 交易额 | 价格变化 |\n"

    for index, token in enumerate(top_token_list):
        ca = token['token']['address']
        n = token['token']['symbol'][:5]
        liq = format_number(int(token['liquidity']))
        mc = format_number(int(token['marketCap']))
        v = format_number(int(token[f'volume{interval}']))
        p = round(float(token[f'change{interval}']) * 100)

        # 创建每行的数据
        res += f"| *{index + 1}.*[{n}](https://debot.ai/token/solana/{ca}) | *{liq}* | *{mc}* | *{v}* | *{p}%* |\n"
    return res


def return_buyCount_token(interval, top_token_list):
    inter = interval if interval == '5m' else interval + "h"
    res = f"🦾*{inter} 买单排行榜：*\n"
    res += f"| Token | 池子 | 市值 | 交易量 | 交易额 | 价格变化 |\n"

    for index, token in enumerate(top_token_list):
        ca = token['token']['address']
        n = token['token']['symbol'][:5]
        liq = format_number(int(token['liquidity']))
        mc = format_number(int(token['marketCap']))
        txn = token[f'txnCount{interval}']
        v = format_number(int(token[f'volume{interval}']))
        p = round(float(token[f'change{interval}']) * 100)

        # 创建每行的数据
        res += f"| *{index + 1}.*[{n}](https://debot.ai/token/solana/{ca}) | *{liq}* | *{mc}* | *{txn}* | *{v}* | *{p}%* |\n"
    return res


def return_pc_token(interval, top_token_list):
    inter = interval if interval == '5m' else interval + "h"
    res = f"📈*{inter} 价格变化排行榜：*\n"
    res += f"| Token | 池子 | 市值 | 交易量 | 价格变化 |\n"

    for index, token in enumerate(top_token_list):
        ca = token['token']['address']
        n = token['token']['symbol'][:5]
        liq = format_number(int(token['liquidity']))
        mc = format_number(int(token['marketCap']))
        v = format_number(int(token[f'volume{interval}']))
        p = round(float(token[f'change{interval}']) * 100)

        # 创建每行的数据
        res += f"| *{index + 1}.*[{n}](https://debot.ai/token/solana/{ca}) | *{liq}* | *{mc}*| *{v}* | *{p}%* |\n"
    return res


def return_vc_token(interval, top_token_list):
    inter = interval if interval == '5m' else interval + "h"
    res = f"💥*{inter} 交易量变化排行榜：*\n"
    res += f"| Token | 池子 | 市值 | 交易量变化 | 价格变化 |\n"

    for index, token in enumerate(top_token_list):
        ca = token['token']['address']
        n = token['token']['symbol'][:5]
        liq = format_number(int(token['liquidity']))
        mc = format_number(int(token['marketCap']))
        vc = round(float(token[f'volumeChange{interval}']) * 100)
        p = round(float(token[f'change{interval}']) * 100)

        # 创建每行的数据
        res += f"| *{index + 1}.*[{n}](https://debot.ai/token/solana/{ca}) | *{liq}* | *{mc}*| *{vc}%* | *{p}%* |\n"
    return res


def return_holders_token(interval, top_token_list):
    inter = interval if interval == '5m' else interval + "h"
    res = f"🐋*{inter} holder排行榜：*\n"
    res += f"| Token | 池子 | 市值 | holder | 价格变化 |\n"

    for index, token in enumerate(top_token_list):
        ca = token['token']['address']
        n = token['token']['symbol'][:5]
        liq = format_number(int(token['liquidity']))
        mc = format_number(int(token['marketCap']))
        holder = format_number(int(token['holders']))
        p = round(float(token[f'change{interval}']) * 100)

        # 创建每行的数据
        res += f"| *{index + 1}.*[{n}](https://debot.ai/token/solana/{ca}) | *{liq}* | *{mc}*| *{holder}* | *{p}%* |\n"
    return res


def get_new_token():
    try:
        response = requests.get(
            "https://api.dexscreener.com/token-profiles/latest/v1",
            headers={},
        )
        data = response.json()
        res = []
        for token in data:
            if token['chainId'] == 'solana':
                res.append(token)
        return res
    except Exception as e:
        safe_send_message(chat_id_alert, f"获取新币时出现错误{e}")
        return None


def get_latest_boosted_token():
    try:
        response = requests.get(
            "https://api.dexscreener.com/token-boosts/latest/v1",
            headers={},
        )
        data = response.json()
        res = []
        for token in data:
            if token['chainId'] == 'solana':
                res.append(token)
        return res
    except Exception as e:
        safe_send_message(chat_id_alert, f"获取新boost时出现错误{e}")
        return None


def get_new_token_recommend():
    try:
        res = []
        new_token = get_new_token()
        if not new_token:
            safe_send_message(chat_id_alert, "dex没有获取到新币")
            return None
        top_new_list = get_newest_token(30)
        if not top_new_list:
            safe_send_message(chat_id_alert, "没有获取到新币")
            return None
        merge_list = list(set([token['tokenAddress'] for token in new_token] + [token['token']['address'] for token in
                                                                                top_new_list]))

        # latest_boosted_token = get_latest_boosted_token()
        # if not latest_boosted_token:
        #     safe_send_message(chat_id_alert, "没有获取到boost币")
        #     return None
        # merge = {}
        #
        # # 先处理集合 a
        # for item in new_token:
        #     merge[item['tokenAddress']] = [0, 0]
        #
        # # 然后用集合 b 来更新或添加
        # for item in latest_boosted_token:
        #     merge[item['tokenAddress']] = [item['amount'], item['totalAmount']]

        for ca in merge_list:
            if ca not in new_his:
                response = requests.get(
                    f"https://api.dexscreener.com/latest/dex/tokens/{ca}",
                    headers={},
                )
                d = response.json()['pairs']
                if not d:
                    safe_send_message(chat_id_alert, f"new dex未获取到代币信息,ca:{ca}")
                    new_his.add(ca)
                    continue
                for i, data in enumerate(d):
                    if 'liquidity' not in data.keys() or 'fdv' not in data.keys() or 'h24' not in data[
                        'priceChange'].keys():
                        continue
                    elif data['priceChange']['h24'] + 100 >= 1000 and data['fdv'] < 100000000 and data['liquidity'][
                        'usd'] > 50000:
                        pchg = data['priceChange']['h24'] + 100
                        star = 5 if pchg >= 10000 else 4 if pchg >= 5000 else 3 if pchg >= 3000 else 2 if pchg >= 2000 else 1
                        sym = {
                            'ca': ca,
                            'symbol': data['baseToken']['symbol'],
                            'name': data['baseToken']['name'],
                            'price': data['priceUsd'],
                            'liquidity': data['liquidity']['usd'],
                            'fdv': data['fdv'],
                            'pairCreatedAt': data['pairCreatedAt'],
                            'star': star
                            # 'amount': boost[0],
                            # 'totalAmount': boost[1]
                        }
                        res.append(sym)
                        new_his.add(ca)
                    break
            time.sleep(0.5)
        return res
    except Exception as e:
        safe_send_message(chat_id_alert, f"get_latest_token error:{e},ca:{ca}")
        return None


def get_token_age(pair_created_at):
    # 将毫秒时间戳转换为秒（因为 time.time() 返回的是秒级时间戳）
    pair_created_at_seconds = pair_created_at / 1000

    # 获取当前时间（秒级时间戳）
    current_time = datetime.now(timezone.utc).timestamp()

    # 计算时间差（秒数）
    time_diff_seconds = current_time - pair_created_at_seconds

    # 将时间差转换为天、小时、分钟等格式
    days = time_diff_seconds // (24 * 3600)
    hours = (time_diff_seconds % (24 * 3600)) // 3600
    minutes = (time_diff_seconds % 3600) // 60
    seconds = time_diff_seconds % 60
    return f"代币创建了：{int(days)} 天 {int(hours)} 小时 {int(minutes)} 分钟 {int(seconds)} 秒\n"


def scan_new():
    while True:
        try:
            new_list = get_new_token_recommend()
            if new_list is None:
                safe_send_message(chat_id_alert, "本次新币扫描失败")
                time.sleep(60)
                continue
            if len(new_list) > 0:
                sol_sniffer = get_sol_sniffer_datas(new_list)
            for token in new_list:
                age = get_token_age(token['pairCreatedAt'])
                count = count_ca_occurrences(token['ca']) + 1
                liq = format_number(token['liquidity'])
                fdv = format_number(token['fdv'])
                message = f"""
🤖*AI扫链-潜力新币推荐*🧠
🌱*{token['symbol']}*：[{token['name']}](https://debot.ai/token/solana/{token['ca']}) ｜ {token['star'] * "⭐"}
🧮第`{count}`次推送
💧池子：{liq} ｜ 💸市值：{fdv}
💰价格：{token['price']}
⌛{age}
{sol_sniffer.get(token['ca']) if sol_sniffer else ""}
💳*购买入口*：🐸[pepeboost](https://t.me/pepeboost_sol08_bot?start=ref_0samim) | 🐕[debot](https://t.me/trading_solana_debot?start=invite_222966) | 🦅[xxyy](https://xxyy.io/?ref=2CrabsinABottle
)
{"-" * 48}
    """
                safe_send_message(chat_id, message)

                timestamp, push_time = get_utc8_time()

                # 获取当前文件名
                record_file_path = get_current_filename()

                # 检查文件是否存在
                file_exists = os.path.exists(record_file_path)

                new_row = [timestamp, push_time, 1, token['ca'], token['symbol'], token['name'], liq,
                           fdv, token['price'], age, token['star'], count]

                # 打开文件以追加模式
                with open(record_file_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    # 如果文件不存在，写入表头
                    if not file_exists:
                        writer.writerow(COLUMNS)
                    # 写入新行
                    writer.writerow(new_row)
                time.sleep(1)
            time.sleep(120)
        except Exception as e:
            safe_send_message(chat_id_alert, f"AI扫链获取出错：{e}")
            time.sleep(3)
            continue


def get_boosted_token():
    response = requests.get(
        "https://api.dexscreener.com/token-boosts/top/v1",
        headers={},
    )
    data = response.json()
    res = []
    for token in data:
        if token['chainId'] == 'solana':
            res.append(token)
    return res


def flatten_dict(d):
    # 获取 token 字典（如果不存在则返回空字典）
    token_dict = d.get('token', {})
    # 创建新字典，合并 token 字典和其他顶层键值对（排除 token）
    result = {**token_dict, **{k: v for k, v in d.items() if k != 'token'}}
    return result


def format_from_first_nonzero(number, digits=4):
    # 转换为字符串并保留小数部分
    num_str = f"{float(number):.20f}".rstrip('0')
    integer_part, _, decimal_part = num_str.partition('.')

    if not decimal_part:
        return f"{integer_part}.{'0' * digits}"

    # 找到第一个非零数字的索引
    first_nonzero_idx = -1
    for i, digit in enumerate(decimal_part):
        if digit != '0':
            first_nonzero_idx = i
            break

    if first_nonzero_idx == -1:
        return f"{integer_part}.{'0' * digits}"

    # 从第一个非零数字开始，取 digits 位
    result = decimal_part[first_nonzero_idx:first_nonzero_idx + digits]
    # 如果不足 digits 位，补零
    result = result.ljust(digits, '0')
    # 保留原始前导零
    return f"{integer_part}.{decimal_part[:first_nonzero_idx]}{result}"


def token_recommend():
    res = []
    top_list = get_top_token(30, 1)
    boost_list = get_boosted_token()
    merge = {}

    # 先处理集合 a
    for item in top_list:
        merge[item['token']['address']] = 0

    # 然后用集合 b 来更新或添加
    for item in boost_list:
        merge[item['tokenAddress']] = item['totalAmount']

    for ca, amount in merge.items():
        if ca.startswith('0x'):
            continue
        if ca + "|" + str(amount) not in recommend_his:
            response = requests.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{ca}",
                headers={},
            )
            d = response.json()['pairs']
            if not d:
                safe_send_message(chat_id_alert, f"recommend dex未获取到代币信息,ca:{ca}")
                recommend_his.add(ca + "|" + str(amount))
                continue
            # 有可能会有pump.fun的池子放在前面，没有liquidity这个字段
            for data in d:
                if 'liquidity' not in data.keys() or 'fdv' not in data.keys():
                    continue
                elif data['fdv'] < 100000000 and data.get('liquidity', {'usd': 0})['usd'] > 50000 and \
                        data['priceChange'].get('m5', 0) > 0 and data['priceChange'].get('h1', 0) > 0 and \
                        data['priceChange'].get('h6', 0) > 0 and data['priceChange'].get('h24', 0) > 0:
                    sym = {
                        'ca': ca,
                        'symbol': data['baseToken']['symbol'],
                        'name': data['baseToken']['name'],
                        'price': data['priceUsd'],
                        'liquidity': data['liquidity']['usd'],
                        'fdv': data['fdv'],
                        'pairCreatedAt': data['pairCreatedAt'],
                        'txns': data['txns'],
                        'volume': data['volume'],
                        'priceChange': data['priceChange'],
                        'boost_amount': amount
                    }
                    res.append(sym)
                    recommend_his.add(ca + "|" + str(amount))
                break
    return res


def recommend_scan():
    while True:
        try:
            rec_list = token_recommend()
            for token in rec_list:
                #             buy5 = token.get('txns', {}).get('m5', {}).get('buys', 0)
                #             sell5 = token.get('txns', {}).get('m5', {}).get('sells', 0)
                #             pchg5 = format_number(token.get('priceChange', {}).get('m5', 0), True)
                #             buy1 = token.get('txns', {}).get('h1', {}).get('buys', 0)
                #             sell1 = token.get('txns', {}).get('h1', {}).get('sells', 0)
                #             pchg1 = format_number(token.get('priceChange', {}).get('h1', 0), True)
                #             buy6 = token.get('txns', {}).get('h6', {}).get('buys', 0)
                #             sell6 = token.get('txns', {}).get('h6', {}).get('sells', 0)
                #             pchg6 = format_number(token.get('priceChange', {}).get('h6', 0), True)
                #             buy24 = token.get('txns', {}).get('h24', {}).get('buys', 0)
                #             sell24 = token.get('txns', {}).get('h24', {}).get('sells', 0)
                #             pchg24 = format_number(token.get('priceChange', {}).get('h24', 0), True)
                #             v5 = format_number(token.get('volume', {}).get('m5', 0), True)
                #             v1 = format_number(token.get('volume', {}).get('h1', 0), True)
                #             v6 = format_number(token.get('volume', {}).get('h6', 0), True)
                #             v24 = format_number(token.get('volume', {}).get('h24', 0), True)
                #             table = f"""
                #    |  P%  Vol    B/S
                # -----------------------
                # 5m |  {pchg5}   {v5}   {format_number(buy5)}/{format_number(sell5)}
                # 1h |  {pchg1}  {v1}  {format_number(buy1)}/{format_number(sell1)}
                # 6h |  {pchg6}  {v6}  {format_number(buy6)}/{format_number(sell6)}
                # 24h|  {pchg24}  {v24}  {format_number(buy24)}/{format_number(sell24)}
                # """
                age = get_token_age(token['pairCreatedAt'])
                count = count_ca_occurrences(token['ca']) + 1
                liq = format_number(token['liquidity'])
                fdv = format_number(token['fdv'])
                message = f"""
🥇*AI严选-金狗挖掘*🚜
🐕*{token['symbol']}*：[{token['name']}](https://debot.ai/token/solana/{token['ca']}) | ⚡️{token['boost_amount']}
🧮第`{count}`次推送
💧池子：{liq} ｜ 💸市值：{fdv}
💰价格：{token['price']}
⌛{age}
💳*购买入口*：🐸[pepeboost](https://t.me/pepeboost_sol08_bot?start=ref_0samim) | 🐕[debot](https://t.me/trading_solana_debot?start=invite_222966) | 🦅[xxyy](https://xxyy.io/?ref=2CrabsinABottle
)
{"-" * 48}
                """
                safe_send_message(chat_id, message)
                timestamp, push_time = get_utc8_time()

                # 获取当前文件名
                record_file_path = get_current_filename()

                # 检查文件是否存在
                file_exists = os.path.exists(record_file_path)

                new_row = [timestamp, push_time, 2, token['ca'], token['symbol'], token['name'], liq,
                           fdv, token['price'], age, token['boost_amount'], count]

                # 打开文件以追加模式
                with open(record_file_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    # 如果文件不存在，写入表头
                    if not file_exists:
                        writer.writerow(COLUMNS)
                    # 写入新行
                    writer.writerow(new_row)
                time.sleep(1)
            time.sleep(120)
        except Exception as e:
            safe_send_message(chat_id_alert, f"金狗挖掘获取出错：{e}")
            time.sleep(3)
            continue


def return_ca_info(ca):
    try:
        response = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{ca}",
            headers={},
        )
        d = response.json()['pairs']
        for data in d:
            if 'liquidity' not in data.keys() or 'fdv' not in data.keys():
                continue
            else:
                symbol = data['baseToken']['symbol']
                name = data['baseToken']['name'],
                price = data['priceUsd'],
                liquidity = data['liquidity']['usd'],
                fdv = data['fdv'],
                pair_created_at = data['pairCreatedAt'],
                message = f"""
🪙*{symbol}*：[{name[0]}](https://debot.ai/token/solana/{ca})
💧池子：{format_number(liquidity[0])} ｜ 💸市值：{format_number(fdv[0])}
💰价格：{price[0]}
⌛{get_token_age(pair_created_at[0])}
{get_sol_sniffer_data(ca)}
💳*购买入口*：🐸[pepeboost](https://t.me/pepeboost_sol08_bot?start=ref_0samim) | 🐕[debot](https://t.me/trading_solana_debot?start=invite_222966) | 🦅[xxyy](https://xxyy.io/?ref=2CrabsinABottle
)
{"-" * 48}
                            """
                return message
    except Exception as e:
        print(e)
        return None


@bot.message_handler(func=lambda message: message.text and message.text.startswith('/top'))
@restricted
def get_top(message):
    """
    :param message: 用户输入/top12 v 则会按照交易量排前12，如果不写，就默认按照热门排序前10
                    时间节点输入为 5m 1 4 12 24 分别代表 5m, 1h, 4h, 12h, 24h
    :return:
    """
    try:
        if not message.text:
            bot.reply_to(message, "命令不能为空，请输入正确的格式！示例：/top10 5m v")
            return

        limit = 10
        is_volume_based = False
        # 分割用户输入内容
        parts = message.text.split()

        # 检查命令是否是类似 /top10
        if parts[0].startswith('/top') and parts[0][4:].isdigit():
            limit = int(parts[0][4:])  # 提取 /top 后的数字部分

        interval = parts[1] if len(parts) > 1 else "1"

        # 检查是否有 'v' 参数
        if len(parts) > 2:
            if parts[2] == 'v':
                is_volume_based = True
                t = get_top_token(limit=limit, interval=interval, is_volume_based=is_volume_based)
                if t is None:
                    bot.reply_to(message, "无法获取代币数据，请稍后再试！")
                    return

                # 返回代币结果
                data = return_top_token(interval, t, is_volume_based)
                if data is None:
                    bot.reply_to(message, "获取结果为空，请检查参数后重试！")
                    return

                # 发送信息
                safe_send_message(chat_id, data)
            elif parts[2] == 'b':
                t = get_rank_buyCount(limit, interval)
                if t is None:
                    bot.reply_to(message, "无法获取代币数据，请稍后再试！")
                    return
                data = return_buyCount_token(interval, t)
                if data is None:
                    bot.reply_to(message, "获取结果为空，请检查参数后重试！")
                    return
                safe_send_message(chat_id, data)
            elif parts[2] == 'h':
                t = get_rank_holder(limit, interval)
                if t is None:
                    bot.reply_to(message, "无法获取代币数据，请稍后再试！")
                    return
                data = return_holders_token(interval, t)
                if data is None:
                    bot.reply_to(message, "获取结果为空，请检查参数后重试！")
                    return
                safe_send_message(chat_id, data)
            elif parts[2] == 'vc':
                t = get_rank_vc(limit, interval)
                if t is None:
                    bot.reply_to(message, "无法获取代币数据，请稍后再试！")
                    return
                data = return_vc_token(interval, t)
                if data is None:
                    bot.reply_to(message, "获取结果为空，请检查参数后重试！")
                    return
                safe_send_message(chat_id, data)
            elif parts[2] == 'pc':
                t = get_rank_pc(limit, interval)
                if t is None:
                    bot.reply_to(message, "无法获取代币数据，请稍后再试！")
                    return
                data = return_pc_token(interval, t)
                if data is None:
                    bot.reply_to(message, "获取结果为空，请检查参数后重试！")
                    return
                safe_send_message(chat_id, data)
        else:
            t = get_top_token(limit=limit, interval=interval, is_volume_based=is_volume_based)
            if t is None:
                bot.reply_to(message, "无法获取代币数据，请稍后再试！")
                return

            # 返回代币结果
            data = return_top_token(interval, t, is_volume_based)
            if data is None:
                bot.reply_to(message, "获取结果为空，请检查参数后重试！")
                return

            # 发送信息
            safe_send_message(chat_id, data)

    except Exception as e:
        print(f"Error occurred: {e}")
        bot.reply_to(message, "请输入正确的参数格式。示例：/top10 5m v")


# @bot.message_handler(func=lambda msg: not msg.text.startswith('/'))
# def echo_all(message):
#     res = return_ca_info(message.text)
#     safe_send_message(chat_id, res) if len(res) else safe_send_message(chat_id, "未查询到合约信息")


def start_bot():
    while True:
        try:
            bot.session = session
            bot.delete_webhook()
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            print(f"Bot Error occurred: {e}")
            bot.stop_polling()
            time.sleep(5)  # 等待5秒后重新启动
            continue


def get_vc_increase(limit=10):
    while True:
        try:
            a = get_rank_vc(limit, '1')
            b = get_rank_vc(limit, '5m')
            m = []
            res = []
            for token in a:
                m.append(token['token']['address'])
            for token in b:
                if token['token']['address'] in m:
                    res.append(token)
            for token in res:
                if str(token) in vc_increase_his:
                    continue
                ca = token['token']['address']
                symbol = token['token']['symbol']
                name = token['token']['name']
                age = get_token_age(token['createdAt'] * 1000)
                vc = round(float(token['volumeChange5m']) * 100)
                liq = format_number(int(token['liquidity']))
                mc = format_number(int(token['marketCap']))
                price = format_from_first_nonzero(token['priceUSD'])
                count = count_ca_occurrences(ca) + 1
                message = f"""
🚀*AI脉冲警报*🔥
🎈*{symbol}*：[{name}](https://debot.ai/token/solana/{ca}) | 💥{vc}%
🧮第`{count}`次推送
💧池子：{liq} ｜ 💸市值：{mc}
💰价格：{price}
⌛{age}
💳*购买入口*：🐸[pepeboost](https://t.me/pepeboost_sol08_bot?start=ref_0samim) | 🐕[debot](https://t.me/trading_solana_debot?start=invite_222966) | 🦅[xxyy](https://xxyy.io/?ref=2CrabsinABottle
)
{"-" * 48}
        """
                safe_send_message(chat_id, message)
                timestamp, push_time = get_utc8_time()

                # 获取当前文件名
                record_file_path = get_current_filename()

                # 检查文件是否存在
                file_exists = os.path.exists(record_file_path)

                new_row = [timestamp, push_time, 3, ca, symbol, name, liq, mc, price, age, vc, count]

                # 打开文件以追加模式
                with open(record_file_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    # 如果文件不存在，写入表头
                    if not file_exists:
                        writer.writerow(COLUMNS)
                    # 写入新行
                    writer.writerow(new_row)
                vc_increase_his.add(str(token))
                time.sleep(1)
            time.sleep(150)
        except Exception as e:
            safe_send_message(chat_id_alert, f"AI脉冲警报获取出错：{e}")
            time.sleep(3)
            continue


def get_token_chart(ca, st, interval, network_id=sol_id, url="https://graph.defined.fi/graphql"):
    try:
        symbol = f'{ca}:{network_id}'
        now_time, now_str = get_utc8_time()
        getTopToken = f"""query {{
          getBars(
            symbol:"{symbol}",
            from: {st},
            to:{now_time},
            resolution:"{interval}"
          ) {{
            o
            h
            l
            c
            s
            liquidity
          }}
        }}"""
        response = requests.post(url, headers=headers3, json={"query": getTopToken})
        res = json.loads(response.text)
        res_list = res['data']['getBars']
        return res_list
    except BaseException as e:
        safe_send_message(chat_id_alert, f"getBars error:{e}")
        return None


def process_csv(last_hours=24, near_hours=0):
    try:
        files = glob.glob(os.path.join(current_dir, f"{BASE_FILENAME}_*{FILE_EXTENSION}"))

        # 使用正则表达式提取文件名中的数字索引
        index_pattern = re.compile(rf"{BASE_FILENAME}_(\d+){FILE_EXTENSION}")
        file_indices = []
        for file in files:
            match = index_pattern.search(os.path.basename(file))
            if match:
                index = int(match.group(1))  # 提取数字索引
                file_indices.append((file, index))

        # 按索引降序排序（索引最大的排在前面）
        file_indices.sort(key=lambda x: x[1], reverse=True)

        # 选择索引最大的两个文件（如果只有一个，则只选一个）
        selected_files = [file for file, _ in file_indices[:2]]

        # 读取并拼接文件为 DataFrame
        if not selected_files:
            safe_send_message(chat_id_alert, "没有找到匹配的文件。")
            df = pd.DataFrame()  # 如果没有文件，返回空 DataFrame
        elif len(selected_files) == 1:
            df = pd.read_csv(selected_files[0])
        else:
            # 读取两个文件并拼接
            df1 = pd.read_csv(selected_files[0])
            df2 = pd.read_csv(selected_files[1])
            df = pd.concat([df1, df2], ignore_index=True)

        # 验证列名
        if not all(col in df.columns for col in COLUMNS):
            safe_send_message(chat_id_alert, f"CSV 文件缺少必要的列：{set(COLUMNS) - set(df.columns)}")

        # 1. 时间筛选
        # 获取当前时间（北京时间，UTC+8）
        utc8 = timezone(timedelta(hours=8))
        now = datetime.now(utc8)
        # 当前时间戳（秒）
        now_timestamp = int(now.timestamp())
        # 计算时间范围：过去 n 小时到过去 2 小时（时间戳，秒）
        start_time = now_timestamp - last_hours * 3600
        end_time = now_timestamp - near_hours * 3600

        # 调试：打印时间戳范围（转换为可读时间）
        st = datetime.fromtimestamp(start_time, utc8).strftime('%Y-%m-%d %H:%M')
        et = datetime.fromtimestamp(end_time, utc8).strftime('%Y-%m-%d %H:%M')
        safe_send_message(chat_id_alert, f"筛选时间戳范围：{start_time} ({st}) "
                                         f"到 {end_time} ({et})")
        output_file = os.path.join(current_dir, f"p_{st}__{et}.csv")

        # 确保 timestamp 是整数（Unix 时间戳）
        df['timestamp'] = df['timestamp'].astype(int)

        # 筛选 timestamp 在 [start_time, end_time] 内的记录
        df = df[(df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)]

        # 调试：打印筛选后的记录数
        safe_send_message(chat_id_alert, f"筛选后记录数：{len(df)}")

        if df.empty:
            safe_send_message(chat_id_alert, "警告：筛选后没有数据，请检查时间范围或 timestamp 数据")
            return None

        # 2. 统计每个 ca 的 type 出现次数
        type_counts = df.groupby(['ca', 'type']).size().unstack(fill_value=0)

        # 重命名列：将 1, 2, 3 映射到 type1count, type2count, type3count
        type_counts.columns = [f'type{int(col)}count' for col in type_counts.columns]

        # 确保 type1count, type2count, type3count 存在，缺失的列填充 0
        for col in ['type1count', 'type2count', 'type3count']:
            if col not in type_counts.columns:
                type_counts[col] = 0

        type_counts = type_counts.reset_index()

        # 3. 合并 type 计数到原始 DataFrame
        df = df.merge(type_counts, on='ca', how='left')

        # 4. 按 ca 去重，保留 price 最低的记录
        df_sorted = df.sort_values(['ca', 'price'])
        df_dedup = df_sorted.groupby('ca').first().reset_index()

        # 5. 确保输出包含所有原始列和计数列
        expected_columns = COLUMNS + ['type1count', 'type2count', 'type3count']
        df_dedup = df_dedup[expected_columns]

        # 6. 保存结果到 CSV
        df_dedup.to_csv(output_file, index=False, encoding='utf-8')
        safe_send_message(chat_id_alert, f"处理完成，结果已保存")

        return output_file

    except FileNotFoundError:
        safe_send_message(chat_id_alert, f"错误：源文件未找到")
    except ValueError as e:
        safe_send_message(chat_id_alert, f"错误：{str(e)}")
    except Exception as e:
        safe_send_message(chat_id_alert, f"发生错误：{str(e)}")


def get_push_result_csv(processed_file):
    directory = os.path.dirname(processed_file)  # 获取目录部分
    filename = os.path.basename(processed_file)  # 获取文件名部分

    # 替换文件名开头的第一个字母
    if directory and filename:  # 确保文件名不为空
        result_file = os.path.join(directory, 'r' + filename[1:])
    else:
        safe_send_message(chat_id_alert, "文件名为空")
        return
    with open(processed_file, 'r', newline='') as csvfile, open(result_file, 'w', newline='') as outfile:
        reader = csv.DictReader(csvfile)
        # Ensure CSV file contains timestamp and ca columns
        if 'timestamp' not in reader.fieldnames or 'ca' not in reader.fieldnames:
            safe_send_message(chat_id_alert, "Error: CSV file missing 'timestamp' or 'ca' column")
            exit()

        # Add new columns to fieldnames
        fieldnames = reader.fieldnames + ['high_ratio', 'now_ratio']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        # Process rows in batches
        while True:
            batch = list(islice(reader, 5))
            if not batch:
                break  # No more rows to process

            for row in batch:
                timestamp = row['timestamp']
                ca = row['ca']
                price = float(row['price'])
                res = get_token_chart(ca, timestamp, 5)
                # 说明是其他链条的
                if not res:
                    continue
                if not res['o'][0]:
                    safe_send_message(chat_id_alert, f"getBars 获取了None数据，ca:{ca}")
                    continue
                hl = res['h']
                h = sorted(hl, reverse=True)[1]
                c = res['c'][-1]
                liq = float(res['liquidity'][-1])

                # Copy original row
                new_row = row.copy()
                if liq < 10000:
                    new_row['high_ratio'] = -911
                    new_row['now_ratio'] = -911
                else:
                    high_ratio = round(h / price * 100, 2)
                    now_ratio = round(c / price * 100, 2)
                    new_row['high_ratio'] = high_ratio
                    new_row['now_ratio'] = now_ratio

                writer.writerow(new_row)

                # Sleep to respect API rate limit (5 requests per second)
                time.sleep(0.2)

            # Optional: Add a small buffer after each batch
            time.sleep(0.1)
    safe_send_message(chat_id_alert, "战绩结果写入完成")
    safe_send_message(chat_id_alert, "生成统计图中……")

    df = pd.read_csv(result_file)

    # 提取小时部分，用于分组
    df['time'] = pd.to_datetime(df['time'], format='%Y-%m-%d %H:%M:%S')
    df['hour'] = df['time'].dt.hour
    # 计算 -911 的记录数，按小时分组
    count_911 = df[df['high_ratio'] == -911].groupby('hour').size().reset_index(name='count_scam')

    # 过滤掉 high_ratio 等于 -911 的记录，计算平均 high_ratio
    df_filtered = df[df['high_ratio'] != -911]
    hourly_avg = df_filtered.groupby('hour')['high_ratio'].mean().reset_index()

    # 合并数据，确保所有小时都出现（即使某些小时无数据）
    all_hours = pd.DataFrame({'hour': range(24)})
    hourly_avg = all_hours.merge(hourly_avg, on='hour', how='left')
    count_911 = all_hours.merge(count_911, on='hour', how='left').fillna({'count_911': 0})

    # 绘制柱状图
    fig, ax1 = plt.subplots(figsize=(16, 8))

    # 设置柱子宽度和偏移
    bar_width = 0.35
    spacing = 0.05
    hours = hourly_avg['hour']

    # 定义浅蓝色和浅红色
    light_blue = '#6495ED'  # 柔和的浅蓝色
    light_red = '#FF4040'  # 柔和的浅红色

    # 绘制蓝色柱子（平均 high_ratio，左侧纵轴）
    bars_avg = ax1.bar(hours - bar_width / 2, hourly_avg['high_ratio'].fillna(0), bar_width,
                       label='Average High Ratio (Excl. Scam)', color=light_blue)

    # 创建右侧纵轴并绘制红色柱子（-911 计数）
    ax2 = ax1.twinx()
    bars_911 = ax2.bar(hours + bar_width / 2, count_911['count_scam'], bar_width, label='Scam Count',
                       color=light_red)

    # 计算动态偏移量（基于 high_ratio 范围的 2% 和 count_911 的 2%）
    max_height_avg = max(abs(hourly_avg['high_ratio'].max()), abs(hourly_avg['high_ratio'].min()), 0.1)
    offset_avg = 0.02 * max_height_avg
    max_height_911 = max(count_911['count_scam'].max(), 1)  # 至少为 1
    offset_911 = 0.02 * max_height_911

    # 为蓝色柱子添加标签（正值在上方，负值在下方）
    for bar in bars_avg:
        yval = bar.get_height()
        if yval > 0:  # 正值：显示在柱子上方
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                yval + offset_avg,
                f'{yval:.0f}%' if yval != 0 else '',
                ha='center',
                va='bottom',
                fontsize=8,
                color='blue'
            )
        elif yval < 0:  # 负值：显示在柱子下方
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                yval - offset_avg,
                f'{yval:.0f}%',
                ha='center',
                va='top',
                fontsize=8,
                color='blue'
            )

    # 为红色柱子添加标签（在上方，整数）
    for bar in bars_911:
        yval = bar.get_height()
        if yval > 0:  # 仅非零计数显示标签
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                yval + offset_911,
                f'{int(yval)}',
                ha='center',
                va='bottom',
                fontsize=8,
                color='red'
            )

    # 设置轴标签和标题
    ax1.set_xlabel('Hour (e.g., 1 represents 1:00-2:00)')
    ax1.set_ylabel('Average High Ratio', color='blue')
    ax2.set_ylabel('Count of Scam', color='red')
    plt.title('Average High Ratio and Scam Count per Hour Segment')

    # 设置横轴为整数小时点（0, 1, 2, ...）
    ax1.set_xticks(hours)
    ax1.set_xticklabels(hours, rotation=0)

    # 设置颜色和网格
    ax1.tick_params(axis='y', labelcolor='blue')
    ax2.tick_params(axis='y', labelcolor='red')
    ax1.grid(True, axis='y', linestyle='--', alpha=0.7)

    # 添加图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    plt.tight_layout()

    # 添加上方中间水印
    plt.text(
        0.5, 0.85,  # x=0.5（水平居中），y=0.95（靠近顶部）
        "@EttoroSummer Copyright",  # 更长的文字
        fontsize=30,  # 字体更大
        alpha=0.5,  # 透明度
        color="gray",
        ha="center",  # 水平居中
        va="center",  # 垂直居中
        rotation=0,  # 不旋转（或根据需要调整）
        transform=plt.gcf().transFigure  # 使用整个图的坐标系
    )

    # 添加下方中间水印
    plt.text(
        0.5, 0.15,  # x=0.5（水平居中），y=0.05（靠近底部）
        "@EttoroSummer Copyright",  # 更长的文字
        fontsize=30,  # 字体更大
        alpha=0.5,  # 透明度
        color="gray",
        ha="center",  # 水平居中
        va="center",  # 垂直居中
        rotation=0,  # 不旋转
        transform=plt.gcf().transFigure
    )

    # 保存到内存
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    safe_send_message(chat_id_alert, "统计图生成成功……")
    return result_file, buf


@bot.message_handler(commands=['csv'])
@restricted
def get_csv(message):
    try:
        if not message.text:
            bot.reply_to(message, "命令不能为空，请输入正确的格式！示例：/csv 24 0")
            return

        # 分割用户输入内容
        parts = message.text.split()
        if len(parts) == 1:
            last_hours, near_hours = 24, 0
        elif len(parts) == 2:
            bot.reply_to(message, "请输入正确的参数格式。示例：/csv 24 0")
            return
        else:
            last_hours = int(parts[1])  # 第一个参数
            near_hours = int(parts[2])  # 第二个参数
        processed_file = process_csv(last_hours, near_hours)
        res_file, buf = get_push_result_csv(processed_file)
        if os.path.getsize(res_file) > 50 * 1024 * 1024:  # 50MB
            bot.reply_to(message, "文件过大，请联系管理员处理！")
            return
        else:
            # 发送 CSV 文件给用户
            with open(res_file, 'rb') as file:
                bot.send_document(
                    chat_id=message.chat.id,
                    document=file,
                    caption="这是您请求的 CSV 文件",
                    reply_to_message_id=message.message_id
                )
            bot.send_photo(
                chat_id=message.chat.id,
                photo=buf
            )
            buf.close()
    except Exception as e:
        bot.reply_to(message, f"请输入正确的参数格式。示例：/csv 24 0 error:{e}")


def delete_pr_files():
    # 获取当前工作目录
    current_dir = os.getcwd()

    # 定义要匹配的文件模式
    patterns = ['p_*.csv', 'r_*.csv']

    # 遍历所有匹配模式
    for pattern in patterns:
        # 查找匹配模式的文件
        files_to_delete = glob.glob(os.path.join(current_dir, pattern))

        # 删除每个匹配的文件
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
                print(f"已删除: {file_path}")
            except OSError as e:
                print(f"删除 {file_path} 失败: {e}")

    # 检查是否删除了文件
    if not files_to_delete:
        print("没有找到符合条件的文件（以 'p_' 或 'r_' 开头、'.csv' 结尾）。")


if __name__ == "__main__":
    new_his = set()
    recommend_his = set()
    vc_increase_his = set()

    delete_pr_files()

    # 创建自定义的 session
    session = requests.Session()

    # 增加连接池的大小，并且设置重试机制
    retry_strategy = Retry(
        total=5,  # 最大重试次数
        backoff_factor=2,  # 每次重试间隔的时间倍数
        status_forcelist=[429, 500, 502, 503, 504]  # 针对这些状态码进行重试
    )

    adapter = HTTPAdapter(pool_connections=200, pool_maxsize=200, max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 使用多线程来运行Bot和扫描任务
    bot_thread = threading.Thread(target=start_bot)
    new_thread = threading.Thread(target=scan_new)
    rec_thread = threading.Thread(target=recommend_scan)
    inc_thread = threading.Thread(target=get_vc_increase)

    # 启动两个线程
    bot_thread.start()
    new_thread.start()
    rec_thread.start()
    inc_thread.start()

    # 等待两个线程完成
    bot_thread.join()
    new_thread.join()
    rec_thread.join()
    inc_thread.join()
