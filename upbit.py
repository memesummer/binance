# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2025/3/22 16:52
#    @Description   : 
#
# ===============================================================
import asyncio
import concurrent.futures
import json
import os
import re
import time
from datetime import datetime, timedelta

import aiohttp
import requests
import telebot
from aiolimiter import AsyncLimiter
from requests.adapters import HTTPAdapter
from requests.exceptions import Timeout
from requests.packages.urllib3.util.retry import Retry


def remove_symbols(text):
    # 使用正则表达式，保留字母、数字和空格
    cleaned_text = re.sub(r'[^\w\s]', '', text)
    return cleaned_text


def safe_send_message(chat_id, message):
    try:
        bot.send_message(chat_id, message, timeout=10)  # 设置超时时间为10秒
    except Timeout:
        bot.send_message(chat_id_alert, "发送消息超时，正在重试...")
    except Exception as e:
        bot.send_message(chat_id_alert, f"scan 消息发送失败: {remove_symbols(message)} error:{e}")


def format_number(num):
    if abs(num) >= 1000000000:  # 10亿
        return f"{num / 1000000000:.2f}B"
    elif abs(num) >= 1000000:
        return f"{num / 1000000:.2f}M"
    elif abs(num) >= 1000:
        return f"{num / 1000:.2f}K"
    else:
        return str(num)


def get_upbit_token_list(url="https://api.upbit.com/v1/market/all"):
    # 发送 GET 请求
    response = requests.get(url)

    token = []
    # 检查响应状态
    if response.status_code == 200:
        # 解析 JSON 数据
        data = response.json()
        for i in data:
            token.append(i['market'].split('-')[1])
        # 打印数据（或根据需要处理）
        token = list(set(token))
        return token
    else:
        print(f"请求失败，状态码: {response.status_code}")


def to_list_on_upbit():
    from main import binance_spot_list, binance_future_list
    binance = list(set(list(binance_future_list()) + list(binance_spot_list())))
    upbit = get_upbit_token_list()
    difference = [item[:-4] for item in binance if item[:-4] not in upbit]
    cleaned_difference = list(filter(bool, difference))
    return cleaned_difference


def get_24h_volume(server_url="https://api.upbit.com", rank=10):
    params = {"quote_currencies": "KRW"}

    res = requests.get(server_url + "/v1/ticker/all", params=params)
    res = res.json()
    # 使用 sorted 函数排序
    sorted_data = sorted(
        [x for x in res if x['market'] != 'KRW-USDT'],
        key=lambda x: x['acc_trade_volume_24h'] * x['trade_price'],
        reverse=True
    )

    # 取前十
    top_10 = sorted_data[:rank]

    result = [[item['market'].split('-')[1], round(item['acc_trade_volume_24h'] * item['trade_price'] / 1450, 2),
               round(item['change_rate'] * 100, 2)] for
              item in top_10]
    return result


async def get_upbit_candle_volume(session, market, unit, limiter, retries=3):
    if market == 'KRW-USDT':
        return None
    params = {
        'market': market,
        'count': 1
    }
    headers = {"accept": "application/json"}
    candle_url = f"https://api.upbit.com/v1/candles/minutes/{unit}"

    for attempt in range(retries):
        try:
            async with limiter:
                async with session.get(candle_url, params=params, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        x = (await response.json())[0]
                        volume = x['candle_acc_trade_volume'] * x['trade_price']
                        return [market.split("-")[1], volume]
                    elif response.status == 429:
                        wait_time = 2 ** attempt  # 指数退避：1s, 2s, 4s
                        print(f"{market} 请求过多，第 {attempt + 1} 次重试，等待 {wait_time} 秒")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"{market} 请求失败: {response.status}")
                        return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"请求 {market} 失败: {e}")
            return None
    print(f"{market} 重试 {retries} 次后仍失败")
    return None


async def get_upbit_volume_async(unit, reverse=True, rank=10, ticker_url="https://api.upbit.com/v1/market/all"):
    response = requests.get(ticker_url)
    krw_market = []

    if response.status_code == 200:
        remaining_req = response.headers.get("Remaining-Req")
        if remaining_req:
            print(f"剩余请求信息: {remaining_req}")

            # 解析 Remaining-Req
            parts = remaining_req.split("; ")
            req_dict = {part.split("=")[0]: part.split("=")[1] for part in parts}
            print(f"组: {req_dict['group']}")
            print(f"每分钟剩余请求: {req_dict['min']}")
            print(f"每秒剩余请求: {req_dict['sec']}")
        else:
            print("响应中没有 Remaining-Req 标头")
        data = response.json()
        for i in data:
            if i['market'].startswith("KRW"):
                krw_market.append(i['market'])
        print(f"KRW 市场数量: {len(krw_market)}")
    else:
        print(f"请求失败，状态码: {response.status_code}")
        return

    limiter = AsyncLimiter(8, 1)  # 每秒 10 个请求
    async with aiohttp.ClientSession() as session:
        tasks = [get_upbit_candle_volume(session, symbol, unit, limiter) for symbol in krw_market]
        results = await asyncio.gather(*tasks)
        volume_list = [r for r in results if r is not None]

    sorted_list = sorted(volume_list, key=lambda x: x[1], reverse=reverse)[:rank]
    return [[item[0], round(item[1] / 1450, 2)] for item in sorted_list]


def get_upbit_volume(unit, reverse=True, rank=10, ticker_url="https://api.upbit.com/v1/market/all", m=15, r=30):
    res_24 = get_24h_volume()
    res_unit = asyncio.run(get_upbit_volume_async(unit, reverse, rank, ticker_url))
    res = f"`符号         近24h交易量     24h价格变化`\n"
    for i, l in enumerate(res_24):
        line = f"`{i + 1}.{l[0]}"
        n1 = len(line)
        line += ' ' * (m - n1)
        line += format_number(float(l[1]))
        n2 = len(line)
        line += ' ' * (r - n2)
        line += f"{str(l[2])}%"
        line += '`\n'
        res += line
    res += '\n'
    res += f"`符号         近{unit}m交易量`\n"
    for i, l in enumerate(res_unit):
        line = f"`{i + 1}.{l[0]}"
        n1 = len(line)
        line += ' ' * (m - n1)
        line += format_number(float(l[1]))
        line += '`\n'
        res += line
    return res


def get_15m_upbit_volume(rank=20):
    res_unit = asyncio.run(
        get_upbit_volume_async(15, reverse=True, rank=rank, ticker_url="https://api.upbit.com/v1/market/all"))
    return res_unit


def get_15m_upbit_volume_increase(symbol, unit=15):
    market = 'KRW-' + symbol
    params = {
        'market': market,
        'count': 2
    }
    headers = {"accept": "application/json"}
    candle_url = f"https://api.upbit.com/v1/candles/minutes/{unit}"
    response = requests.get(candle_url, params=params, headers=headers)
    if response.status_code == 200:
        data15 = response.json()
        v_now = float(data15[0]['candle_acc_trade_volume'])
        v_past = float(data15[1]['candle_acc_trade_volume'])
        v_ratio = round(float(v_now / v_past), 2)
        if v_ratio >= 3:
            v15_list = [1, v_ratio]
        else:
            v15_list = [0, v_ratio]
        return v15_list
    else:
        print(f"{market} get_15m_upbit_volume_increase请求失败: {response.status_code}")
        return None


def fetch_large_trades_spot(market, threshold, limit=500):
    url = "https://api.upbit.com/v1/trades/ticks"
    params = {
        'market': market,
        'count': limit
    }
    headers = {"accept": "application/json"}

    response = requests.get(url, params=params, headers=headers)
    if response.status_code == 200:
        st = ""
        trades = response.json()
        for trade in trades:
            if str(trade) not in upbit_his:
                volume = trade['trade_price'] * trade['trade_volume'] / 1450
                if volume > threshold:
                    utc_time = datetime.strptime(f"{trade['trade_date_utc']} {trade['trade_time_utc']}",
                                                 '%Y-%m-%d %H:%M:%S')
                    utc_plus_8_time = utc_time + timedelta(hours=8)
                    trade_time = utc_plus_8_time.strftime('%H:%M:%S')
                    if trade['ask_bid'] == 'ASK':
                        st += f"🟥现货在`{trade_time}`卖出了`{format_number(volume)}`\n"
                    else:
                        st += f"🟩现货在`{trade_time}`买入了`{format_number(volume)}`\n"
                    upbit_his.add(str(trade))
        if not st:
            return ""
        else:
            message = f"""
*🚧symbol：*`{market.split('-')[1]}` 🚧 
{st}
{"-" * 32}
                                                                                    """
            return message
    else:
        print(f"{market} fetch_large_trades_spot请求失败: {response.status_code}")
        return None


def fetch_upbit_tickers(rank, server_url="https://api.upbit.com"):
    params = {"quote_currencies": "KRW"}

    res = requests.get(server_url + "/v1/ticker/all", params=params)
    res = res.json()
    # 使用 sorted 函数排序
    sorted_data = sorted(
        [x for x in res if x['market'] != 'KRW-USDT'],
        key=lambda x: x['change_rate'],
        reverse=True
    )

    # 取前十
    top = sorted_data[:rank]

    result = [item['market'] for
              item in top]
    return result


def get_15m_upbit_volume_increase_str(market, unit=15):
    params = {
        'market': market,
        'count': 3
    }
    headers = {"accept": "application/json"}
    candle_url = f"https://api.upbit.com/v1/candles/minutes/{unit}"
    response = requests.get(candle_url, params=params, headers=headers)
    if response.status_code == 200:
        data15 = response.json()
        v_now = float(data15[0]['candle_acc_trade_volume'])
        v_past = float(data15[1]['candle_acc_trade_volume'])
        v_old = float(data15[2]['candle_acc_trade_volume'])
        if v_past == 0 or v_past < v_old:
            return None
        v_ratio = round(float(v_now / v_past), 2)
        if v_ratio >= 3:
            p = data15[0]['trade_price']
            if data15[0]['trade_price'] > data15[0]['opening_price']:
                emoji = "🔥"
            else:
                emoji = "❄️"
            res = f"""
*💎symbol：*`{market.split('-')[1]}`
💰价格：{p}
🚀{emoji}脉冲指数：`{round(v_ratio * 100, 0)}%`
{"-" * 32}
                        """
            return res
        else:
            return None
    else:
        print(f"{market} get_15m_upbit_volume_increase_str请求失败: {response.status_code}")
        return None


def map_mc_to_threshold(mc):
    if mc < 1:
        return 10000
    elif 1 <= mc < 2:
        return 20000
    elif 2 <= mc < 5:
        return 50000
    elif 5 <= mc < 10:
        return 80000
    else:
        return 100000


if __name__ == "__main__":
    # 配置连接池和重试策略
    retries = Retry(
        total=3,  # 最大重试次数
        backoff_factor=1,  # 重试间隔基数，指数退避
        status_forcelist=[500, 502, 503, 504],  # 遇到这些状态码时重试
    )

    adapter = HTTPAdapter(
        pool_connections=20,  # 连接池中的连接数量
        pool_maxsize=20,  # 最大连接池大小
        max_retries=retries,  # 重试策略
    )

    # 创建 Session 并配置连接池
    session = requests.Session()
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    bot = telebot.TeleBot("6743288280:AAFavxiolz23O50EnrPL1aggeHUNk4NwpJY", parse_mode='Markdown')
    chat_id = "-4679507687"
    chat_id_alert = "-4609875695"

    bot.send_message(chat_id, "开始进行upbit代币推荐......")
    # 设置间隔时间（以秒为单位）
    interval = 300
    last_run = datetime.now()
    flag = True

    upbit_his = set()
    tickers_num = 40
    thresholds = {}

    # 请求间隔（每秒最多 10 次，0.1 秒一个请求）
    REQUEST_DELAY = 0.1

    while True:
        tickers_spot = fetch_upbit_tickers(tickers_num)

        if not tickers_spot:
            time.sleep(10)
            continue

        # 第一部分：处理大单交易
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:  # 减少线程数
            futures = []
            for symbol in tickers_spot:
                if symbol.split("-")[1] in thresholds.keys():
                    threshold = thresholds[symbol.split("-")[1]]
                else:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    token_info_file_path = os.path.join(current_dir, "token_data.json")
                    with open(token_info_file_path, 'r', encoding='utf-8') as json_file:
                        data = json.load(json_file)
                        market_cap = 0
                        for token in data['data']:
                            if token['symbol'].lower() == symbol.split("-")[1].lower():
                                market_cap = round(token['quote']['USD']['market_cap'] / 100000000, 2)
                                break
                    threshold = map_mc_to_threshold(market_cap)
                    thresholds[symbol.split("-")[1]] = threshold

                futures.append(executor.submit(fetch_large_trades_spot, symbol, threshold))
                time.sleep(REQUEST_DELAY)  # 每次提交任务前等待

            for future in concurrent.futures.as_completed(futures):
                message_part = future.result()
                if message_part:
                    safe_send_message(chat_id, message_part)
                    time.sleep(1)

        # 定期清理历史记录
        if len(upbit_his) > 10000:
            upbit_his.clear()

        # 第二部分：15分钟交易量增加检查
        current_time = datetime.now()
        if flag or (current_time - last_run).total_seconds() >= interval:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:  # 减少线程数
                futures = []
                for symbol in tickers_spot:
                    futures.append(executor.submit(get_15m_upbit_volume_increase_str, symbol))
                    time.sleep(REQUEST_DELAY)  # 每次提交任务前等待

                for future in concurrent.futures.as_completed(futures):
                    message_part = future.result()
                    if message_part:
                        safe_send_message(chat_id, message_part)
                        time.sleep(1)
            last_run = current_time
            flag = False

        time.sleep(60)
