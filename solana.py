import json
import re
import threading
import time
from datetime import datetime, timezone

import requests
import telebot
from requests.adapters import HTTPAdapter
from requests.exceptions import Timeout
from urllib3.util.retry import Retry

sol_id = 1399811149
define1 = "1d1cfa84305b78b1ab8cd4205a45f77b231f9686"
define2 = "eab19d30e8cb0d3c39e949aac2dd38ca19da87dc"
codex_api_key = "1d1cfa84305b78b1ab8cd4205a45f77b231f9686"

url = "https://graph.defined.fi/graphql"

headers1 = {
    "content_type": "application/json",
    "Authorization": define1
}
headers2 = {
    "content_type": "application/json",
    "Authorization": define2
}

bot = telebot.TeleBot("8112245267:AAFedRwTwOz06mVqQ6lqRrnwzuvCLRuLFCg", parse_mode='Markdown')
chat_id = "-4629100773"
bot.send_message(chat_id, "开始推荐sol链MEME币......")


def get_if_str(flag):
    if flag:
        return "✅"
    else:
        return "❌"


def get_safe_str(des):
    if des == "high":
        return "🔴—— 高风险：\n"
    elif des == "moderate":
        return "🟡—— 中风险：\n"
    elif des == "low":
        return "🔵—— 低风险：\n"
    elif des == "specific":
        return "🟣—— 特殊风险：\n"
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


def get_sol_sniffer_datas(new_list):
    try:
        ca_list = [i['ca'] for i in new_list]
        url = f'https://solsniffer.com/api/v2/tokens'
        api_key = 'i2e0pwyjlztqemeok2sa6uc2vrk798'

        # 设置请求头，包含API密钥
        headers = {
            'accept': 'application/json',
            # 'Content-Type': 'application/json',
            'X-API-KEY': api_key  # 注意：如果API需要在请求头中发送API密钥
        }
        request_body = {
            "addresses": ca_list
        }

        # 发送GET请求
        response = requests.post(url, headers=headers, json=request_body)

        # 检查响应状态码
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
        else:
            # 如果请求失败，打印错误信息
            print(f"Request failed with status code {response.status_code}")
            print(response.text)
    except Exception as e:
        print(e)
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
        bot.send_message(chat_id, "发送消息超时，正在重试...")
    except Exception as e:
        bot.send_message(chat_id, f"消息发送失败: {remove_symbols(message)}")


def new_pair_parse(res_list, min_liquidity=8000):
    token_list = []
    for token in res_list:
        liq = float(token['liquidity'])
        if liq < min_liquidity:
            continue
        ca1 = token['token0']['id'][:-2]
        ca2 = token['token1']['id'][:-2]
        ca = ca1 if ca2 == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" else ca2
        token_id = 0 if ca2 == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" else 1
        print(token_id)
        pc = round(token['priceChange'], 1)
        if pc <= 0:
            continue
        token_list.append([ca, token_id])
    return token_list


def get_top_token(limit, network_id=sol_id):
    try:
        getTopToken = f"""query {{
          listTopTokens (limit:{limit},networkFilter:{network_id},resolution:"60") {{
            name
            symbol
            address
            volume
            liquidity
            txnCount1
            priceChange1
            uniqueBuys1
            uniqueSells1
            }}
        }}"""
        response = requests.post(url, headers=headers2, json={"query": getTopToken})
        res = json.loads(response.text)
        res_list = res['data']['listTopTokens']
        return res_list
    except BaseException as e:
        print(e)


def return_top_token(top_token_list):
    res = "🔥*1h trending tokens：*\n"
    res += f"| Token | 池子 | 交易量(B/S) | 交易额 | 价格变化 |\n"

    for index, token in enumerate(top_token_list):
        ca = token['address']
        n = token['symbol'][:5]
        liq = format_number(int(token['liquidity']))
        txn = token['txnCount1']
        b = token['uniqueBuys1']
        s = token['uniqueSells1']
        v = format_number(int(token['volume']))
        p = round(token['priceChange1'] * 100)

        # 创建每行的数据
        res += f"| *{index + 1}.*[{n}](https://gmgn.ai/sol/token/{ca}) | *{liq}* | *{txn}*({b}/{s}) | *{v}* | *{p}%* |\n"
    return res


def get_new_token():
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


def get_new_token_recommend():
    res = []
    new_token = get_new_token()
    for token in new_token:
        if token['tokenAddress'] not in new_his:
            response = requests.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{token['tokenAddress']}",
                headers={},
            )
            data = response.json()['pairs'][0]
            if data['priceChange']['h24'] >= 1000 and data['fdv'] < 100000000 and data['liquidity']['usd'] > 10000:
                pchg = data['priceChange']['h24']
                star = 5 if pchg >= 10000 else 4 if pchg >= 5000 else 3 if pchg >= 3000 else 2 if pchg >= 2000 else 1
                sym = {
                    'ca': token['tokenAddress'],
                    'symbol': data['baseToken']['symbol'],
                    'name': data['baseToken']['name'],
                    'price': data['priceUsd'],
                    'liquidity': data['liquidity']['usd'],
                    'fdv': data['fdv'],
                    'pairCreatedAt': data['pairCreatedAt'],
                    'star': star
                }
                res.append(sym)
                new_his.add(token['tokenAddress'])
    return res


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
        message = ""
        new_list = get_new_token_recommend()
        sol_sniffer = get_sol_sniffer_datas(new_list)
        for token in new_list:
            message += f"""
*🌱{token['symbol']}*：[{token['name']}](https://gmgn.ai/sol/token/{token['ca']}) | {token['star'] * "⭐"}
💧池子：{format_number(token['liquidity'])} ｜ 💸市值：{format_number(token['fdv'])}
💰价格：{token['price']}
⌛{get_token_age(token['pairCreatedAt'])}
{sol_sniffer.get(token['ca'])}
{"-" * 32}
"""
        if message:
            safe_send_message(chat_id, message)
        time.sleep(60)


def get_boosted_token():
    response = requests.get(
        "https://api.dexscreener.com/token-boosts/top/v1",
        headers={},
    )
    data = response.json()
    return data


def token_recommend():
    res = []
    top_list = get_top_token(30)
    boost_list = get_boosted_token()
    addresses_from_list1 = {item['address'] for item in top_list}
    addresses_from_list2 = {item['tokenAddress'] for item in boost_list}
    merge = addresses_from_list1.union(addresses_from_list2)

    for ca in merge:
        if ca not in recommend_his:
            response = requests.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{ca}",
                headers={},
            )
            data = response.json()['pairs'][0]
            if data['fdv'] < 100000000 and data['priceChange'].get('m5', 0) > 0 and data['priceChange']['h1'] > 0 and \
                    data['priceChange']['h6'] > 0 and data['priceChange']['h24'] > 0:
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
                    'priceChange': data['priceChange']
                }
                res.append(sym)
                recommend_his.add(ca)
    return res


def recommend_scan():
    while True:
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
            message = f"""
✅ *{token['symbol']}*：[{token['name']}](https://gmgn.ai/sol/token/{token['ca']})
💧池子：{format_number(token['liquidity'])} ｜ 💸市值：{format_number(token['fdv'])}
💰价格：{token['price']}
⌛{get_token_age(token['pairCreatedAt'])}
{"-" * 32}
            """
            safe_send_message(chat_id, message)
            time.sleep(1)
        time.sleep(60)


@bot.message_handler(commands=['top'])
def get_top(message):
    try:
        limit = 10
        t = get_top_token(limit=limit)
        data = return_top_token(t)
        safe_send_message(chat_id, data)
    except Exception as e:
        bot.reply_to(message, "请输入正确的参数格式。示例：/top")


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


if __name__ == "__main__":
    new_his = set()
    recommend_his = set()
    # 创建自定义的 session
    session = requests.Session()

    # 增加连接池的大小，并且设置重试机制
    retry_strategy = Retry(
        total=5,  # 最大重试次数
        backoff_factor=2,  # 每次重试间隔的时间倍数
        status_forcelist=[429, 500, 502, 503, 504],  # 针对这些状态码进行重试
    )

    adapter = HTTPAdapter(pool_connections=200, pool_maxsize=200, max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 使用多线程来运行Bot和扫描任务
    bot_thread = threading.Thread(target=start_bot)
    new_thread = threading.Thread(target=scan_new)
    rec_thread = threading.Thread(target=recommend_scan)

    # 启动两个线程
    bot_thread.start()
    new_thread.start()
    rec_thread.start()

    # 等待两个线程完成
    bot_thread.join()
    new_thread.join()
    rec_thread.join()
