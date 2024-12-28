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


def fetch_bitget_tickers_spot(limit=25):
    url = "https://api.bitget.com/api/v2/spot/market/tickers"

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


def fetch_bitget_tickers_future(limit=25):
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


def fetch_large_trades_spot(symbol, limit=500, threshold=5000):
    thresholds = {"BGB": 50000, "BWB": 10000, "VIRTUAL": 20000}
    threshold = thresholds.get(symbol[:-4], threshold)
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
*🚧symbol：*`{symbol}` 🚧 
{st}
{"-" * 32}
                                                                            """
                return message

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


def fetch_large_trades_future(symbol, threshold=5000):
    thresholds = {"BGB": 50000, "BWB": 10000, "VIRTUAL": 20000}
    threshold = thresholds.get(symbol[:-4], threshold)
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
*🚧symbol：*`{symbol}` 🚧 
{st}
{"-" * 32}
                                                                        """
                return message
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    bitget_his = set()
    binance_list = binance_spot_list()
    while True:
        tickers_spot = fetch_bitget_tickers_spot()
        tickers_future = fetch_bitget_tickers_future()

        if not tickers_spot:
            time.sleep(10)
            continue
        if not tickers_future:
            time.sleep(10)
            continue

        message = ""
        for symbol in tickers_spot:
            if symbol not in binance_list:
                message += fetch_large_trades_spot(symbol)
                if symbol in tickers_future:
                    message += fetch_large_trades_future(symbol)
                    if len(message) >= 3000:
                        safe_send_message(chat_id, message)
                        message = ""
        if message:
            safe_send_message(chat_id, message)
        # 定期清理历史记录，避免内存泄漏
        if len(bitget_his) > 10000:
            bitget_his.clear()

        time.sleep(5)
