# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2025/3/22 16:52
#    @Description   : 
#
# ===============================================================
import asyncio

import aiohttp
import requests
from aiolimiter import AsyncLimiter


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
