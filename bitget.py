import concurrent.futures
import json
import os
import re
import time
from datetime import datetime, timedelta

import requests
import telebot
from requests.adapters import HTTPAdapter
from requests.exceptions import Timeout
from requests.packages.urllib3.util.retry import Retry

from binance_future import format_number
from main import binance_spot_list, symbol1000

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

bot = telebot.TeleBot("7755266537:AAEO5L3L8CVqpi-_3z7BxkCXk4PG0pJ2FM0", parse_mode='Markdown')
chat_id = "-4704065228"
bot.send_message(chat_id, "开始扫描bitget大单......")


def format_price(symbol, price):
    if symbol.startswith("1000") or symbol in symbol1000:
        return price * 1000
    else:
        return price


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
        bot.send_message(chat_id, f"scan 消息发送失败: {remove_symbols(message)}")


def fetch_bitget_tickers_spot(limit=50):
    url = "https://api.bitget.com/api/v2/spot/market/tickers"

    try:
        response = session.get(url, timeout=10)  # 使用自定义 session
        response.raise_for_status()
        data = response.json()
        # 过滤
        fil_str_list = ['USDC', 'FDUSD', 'TUSDUSDT', 'USDP', 'EUR', 'DAI', 'WUSD', 'USDE']

        if data.get("code") == "00000":
            tickers = data.get("data", [])
            usdt_tickers = [ticker for ticker in tickers if
                            ticker["symbol"].endswith("USDT") and all(f not in ticker['symbol'] for f in fil_str_list)]
            sorted_usdt_tickers = sorted(usdt_tickers, key=lambda x: float(x.get("change24h", 0)), reverse=True)
            return [ticker["symbol"] for ticker in sorted_usdt_tickers[:limit]]
        else:
            print(f"Error: {data.get('msg')}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


def fetch_bitget_tickers_future(limit=50):
    url = "https://api.bitget.com/api/v2/mix/market/tickers?productType=USDT-FUTURES"

    try:
        response = session.get(url, timeout=10)  # 使用自定义 session
        response.raise_for_status()
        data = response.json()

        if data.get("code") == "00000":
            tickers = data.get("data", [])
            usdt_tickers = [ticker for ticker in tickers if ticker["symbol"].endswith("USDT")]
            sorted_usdt_tickers = sorted(usdt_tickers, key=lambda x: float(x.get("change24h", 0)), reverse=True)
            return [ticker["symbol"] for ticker in sorted_usdt_tickers[:limit]]
        else:
            print(f"Error: {data.get('msg')}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


def fetch_large_trades_spot(symbol, threshold, limit=500):
    url = "https://api.bitget.com/api/v2/spot/market/fills"
    params = {"symbol": symbol, "limit": limit}

    try:
        response = session.get(url, params=params, timeout=10)  # 使用自定义 session
        response.raise_for_status()
        data = response.json()

        if data.get("code") == "00000":
            st = ""
            trades = data.get("data", [])
            for trade in trades:
                if str(trade) not in bitget_his:
                    price, size = float(trade["price"]), float(trade["size"])
                    volume = price * size
                    if volume > threshold:
                        utc_timestamp = int(trade["ts"]) // 1000
                        utc_plus_8_time = datetime.utcfromtimestamp(utc_timestamp) + timedelta(hours=8)
                        time_only = utc_plus_8_time.strftime("%H:%M")
                        if trade['side'] == 'sell':
                            st += f"🟥现货在`{time_only}`以`{format_price(symbol, price)}`卖出了`{format_number(volume)}`\n"
                        else:
                            st += f"🟩现货在`{time_only}`以`{format_price(symbol, price)}`买入了`{format_number(volume)}`\n"
                        bitget_his.add(str(trade))
            if not st:
                return ""
            else:
                message = f"""
*🚧symbol：*`{symbol[:-4]}` 🚧 
{st}
{"-" * 32}
                                                                            """
                return message

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


def fetch_large_trades_future(symbol, threshold):
    url = "https://api.bitget.com/api/v2/mix/market/fills"
    params = {"symbol": symbol, "productType": 'usdt-futures'}

    try:
        response = session.get(url, params=params, timeout=10)  # 使用自定义 session
        response.raise_for_status()
        data = response.json()

        if data.get("code") == "00000":
            st = ""
            trades = data.get("data", [])
            for trade in trades:
                if str(trade) not in bitget_his:
                    price, size = float(trade["price"]), float(trade["size"])
                    volume = price * size
                    if volume > threshold:
                        utc_timestamp = int(trade["ts"]) // 1000
                        utc_plus_8_time = datetime.utcfromtimestamp(utc_timestamp) + timedelta(hours=8)
                        time_only = utc_plus_8_time.strftime("%H:%M")
                        if trade['side'] == 'sell':
                            st += f"🟥期货在`{time_only}`以`{format_price(symbol, price)}`卖出了`{format_number(volume)}`\n"
                        else:
                            st += f"🟩期货在`{time_only}`以`{format_price(symbol, price)}`买入了`{format_number(volume)}`\n"
                        bitget_his.add(str(trade))
            if not st:
                return ""
            else:
                message = f"""
*🚧symbol：*`{symbol[:-4]}` 🚧 
{st}
{"-" * 32}
                                                                        """
                return message
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


def fetch_whale_buy_ratio(symbol, period='15m'):
    url = "https://api.bitget.com/api/v2/spot/market/fund-flow"
    params = {"symbol": symbol, "period": period}
    try:
        response = session.get(url, params=params, timeout=10)  # 使用自定义 session
        if response.status_code == 429:
            time.sleep(0.5)
            return fetch_whale_buy_ratio(symbol, period)
        elif response.status_code == 400:
            return None  # 跳过当前 symbol

        response.raise_for_status()
        data = response.json()

        if data.get("code") == "00000":
            res = data.get("data", {})
            return [symbol, res.get('whaleBuyRatio', 0), res.get('whaleBuyVolume', 0)]
        else:
            return None  # 过滤掉不符合条件的 symbol
    except requests.exceptions.RequestException as e:
        print(f"Request failed for symbol {symbol}: {e}")
        return None


def get_whale_buy_ratio_rank(interval, rank=10, reverse=True):
    """
    获取所有 symbol 的净成交量排名，顺序请求 API 降低频率
    :param interval: 时间间隔
    :param rank: 返回排名数量
    :param reverse: 排序方式，默认为从高到低
    :return: 排名前的 symbol 列表
    """
    url = "https://api.bitget.com/api/v2/spot/market/tickers"

    try:
        response = session.get(url, timeout=10)  # 使用自定义 session
        response.raise_for_status()
        data = response.json()

        if data.get("code") == "00000":
            tickers = data.get("data", [])
            usdt_tickers = [ticker for ticker in tickers if ticker["symbol"].endswith("USDT")]
            sorted_usdt_tickers = sorted(usdt_tickers, key=lambda x: float(x.get("change24h", 0)), reverse=True)
            spot_tickers = [ticker["symbol"] for ticker in sorted_usdt_tickers[:100]]

        res = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for symbol in spot_tickers:
                futures.append(executor.submit(fetch_whale_buy_ratio, symbol, interval))
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    res.append(result)
                time.sleep(0.5)  # 确保请求频率不超过 1 次/秒

        sorted_list = sorted(res, key=lambda x: x[1], reverse=reverse)[:rank]
        return sorted_list

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return []


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


def get_volume_increase_15_bitget(symbol):
    url = "https://api.bitget.com/api/v2/spot/market/candles"
    params = {"symbol": symbol, "granularity": "15min", "limit": 2}
    try:
        response = session.get(url, params=params, timeout=10)  # 使用自定义 session
        response.raise_for_status()
        data = response.json()

        if data.get("code") == "00000":
            k = data.get("data", [])
            v_now = float(k[1][6])
            v_past = float(k[0][6])
            if v_past == 0:
                return None
            v_ratio = round(float(v_now / v_past), 2)
            if v_ratio >= 5:
                res = f"""
*💎symbol：*`{symbol[:-4]}`
💰价格：{k[1][4]}
🚀近15分钟交易量增长：`{round(v_ratio * 100, 0)}%`
{"-" * 32}
                """
                return res
            else:
                return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


if __name__ == "__main__":
    # 设置间隔时间（以秒为单位）
    interval = 300
    # 使用 datetime 记录上一次执行的时间
    last_run = datetime.now()
    flag = True

    bitget_his = set()
    binance_list = binance_spot_list()
    tickers_num = 50
    # 大写
    thresholds = {'X': 30000, 'SHELL': 12000, 'PI': 80000}
    while True:
        tickers_spot = fetch_bitget_tickers_spot(limit=tickers_num)
        tickers_future = fetch_bitget_tickers_future(limit=tickers_num)

        if not tickers_spot:
            time.sleep(10)
            continue
        if not tickers_future:
            time.sleep(10)
            continue

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for symbol in tickers_spot:
                if symbol not in binance_list:
                    if symbol[:-4] in thresholds.keys():
                        threshold = thresholds[symbol[:-4]]
                    else:
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        token_info_file_path = os.path.join(current_dir, "token_data.json")
                        with open(token_info_file_path, 'r', encoding='utf-8') as json_file:
                            data = json.load(json_file)
                            market_cap = 0
                            for token in data['data']:
                                if token['symbol'].lower() == symbol[:-4].lower():
                                    market_cap = round(token['quote']['USD']['market_cap'] / 100000000, 2)
                                    break
                        threshold = map_mc_to_threshold(market_cap)
                    futures.append(executor.submit(fetch_large_trades_spot, symbol, threshold))
                    if symbol in tickers_future:
                        futures.append(executor.submit(fetch_large_trades_future, symbol, threshold))

            for future in concurrent.futures.as_completed(futures):
                message_part = future.result()
                if message_part:
                    safe_send_message(chat_id, message_part)
                    time.sleep(1)

        # 定期清理历史记录，避免内存泄漏
        if len(bitget_his) > 10000:
            bitget_his.clear()

        current_time = datetime.now()
        if flag or (current_time - last_run).total_seconds() >= interval:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for symbol in tickers_spot:
                    if symbol not in binance_list:
                        futures.append(executor.submit(get_volume_increase_15_bitget, symbol))
                for future in concurrent.futures.as_completed(futures):
                    message_part = future.result()
                    if message_part:
                        safe_send_message(chat_id, message_part)
                        time.sleep(1)
            last_run = current_time
            flag = False

        time.sleep(5)
