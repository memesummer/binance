import concurrent.futures
import json
import os
import re
import time
from datetime import datetime, timedelta

import pytz
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

bot = telebot.TeleBot("7798422656:AAFh0bF8l7vuXUOq3t5b61tBOESpC5VJzW0", parse_mode='Markdown')
chat_id = "-4678705748"
bot.send_message(chat_id, "开始扫描lbank大单......")


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


def lbank_get_top_ticker_info(symbol, base_url, rank):
    """
    获取代币的行情信息
    :param symbol: 代币对，例如 'btc_usdt'
    :param base_url: REST API 基础地址
    :return: 行情信息
    """
    endpoint = f"{base_url}v2/ticker/24hr.do"
    params = {
        "symbol": symbol
    }
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()  # 如果请求失败，将引发异常
        data = response.json()
        if data.get("result") == "true":
            ticker_info = data.get("data")
            if ticker_info:
                # 筛选以 usdt 结尾的 symbol
                filtered_data = [item for item in ticker_info if
                                 item["symbol"].endswith("_usdt") and float(item["ticker"]["turnover"]) > 50000]

                # 按 change 值倒序排序
                sorted_data = sorted(
                    filtered_data,
                    key=lambda x: float(x["ticker"]["change"]),
                    reverse=True
                )

                top_t = sorted_data[:rank]
                symbol_list = [item["symbol"] for item in top_t]
                return symbol_list
            else:
                return None
        else:
            print(f"请求失败，原因: {data.get('error')}")
    except requests.RequestException as e:
        print(f"请求出现异常: {e}")
    return None


def lbank_get_big_trades(symbol, base_url, threshold, size=500):
    endpoint = f"{base_url}v2/supplement/trades.do"
    params = {
        "symbol": symbol,
        "size": size
    }
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()  # 如果请求失败，将引发异常
        data = response.json()
        if data.get("result") == "true":
            trades = data.get("data")
            s = ""
            for trade in trades:
                if str(trade) not in lbank_his:
                    if trade['quoteQty'] > threshold:
                        # 获取系统当前时区
                        local_tz = pytz.timezone(pytz.utc.zone if pytz.utc.zone else 'UTC')

                        # 从 trade 字典中获取时间戳并转换为 UTC 时间
                        utc_timestamp = int(trade["time"]) // 1000
                        utc_time = datetime.utcfromtimestamp(utc_timestamp)

                        # 转换UTC时间到本地时区
                        local_time = utc_time.replace(tzinfo=pytz.utc).astimezone(local_tz)

                        # 判断时间差
                        now = datetime.now(local_tz)  # 获取当前时间在本地时区

                        time_difference = now - local_time

                        # 检查时间差是否小于1小时
                        if time_difference < timedelta(minutes=10):
                            utc_plus_8_time = datetime.utcfromtimestamp(utc_timestamp) + timedelta(hours=8)
                            time_only = utc_plus_8_time.strftime("%H:%M")
                            if trade['isBuyerMaker']:
                                s += f"🟩{symbol[:-5]}在{time_only}以{format_price(symbol, trade['price'])}买入了{format_number(trade['quoteQty'])}\n"
                            else:
                                s += f"🟥{symbol[:-5]}在{time_only}以{format_price(symbol, trade['price'])}卖出了{format_number(trade['quoteQty'])}\n"
                            lbank_his.add(str(trade))
                        else:
                            continue
            if not s:
                return ""
            else:
                message = f"""
*🚧symbol：*`{symbol[:-5]}` 🚧 
{s}
{"-" * 32}
                                                                                                """
                return message
        else:
            print(f"请求失败，原因: {data.get('error')}")
    except requests.RequestException as e:
        print(f"请求出现异常: {e}")
    return None


def map_mc_to_threshold(mc):
    if mc < 0.3:
        return 5000
    elif 0.3 <= mc < 1:
        return 8000
    elif 1 <= mc < 2:
        return 10000
    elif 2 <= mc < 5:
        return 20000
    elif 5 <= mc < 10:
        return 50000
    else:
        return 80000


if __name__ == "__main__":
    lbank_his = set()

    symbol_all = "all"
    base_url = "https://api.lbank.info/"
    rank = 30
    # 小写
    thresholds = {}

    binance_list = binance_spot_list()

    while True:
        ticker_info = lbank_get_top_ticker_info(symbol=symbol_all, base_url=base_url, rank=rank)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for symbol in ticker_info:
                if symbol.replace("_", "").upper() not in binance_list:
                    if symbol[:-5] in thresholds.keys():
                        threshold = thresholds[symbol[:-5]]
                    else:
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        token_info_file_path = os.path.join(current_dir, "token_data.json")
                        with open(token_info_file_path, 'r', encoding='utf-8') as json_file:
                            data = json.load(json_file)
                            market_cap = 0
                            for token in data['data']:
                                if token['symbol'].lower() == symbol[:-5].lower():
                                    market_cap = round(token['quote']['USD']['market_cap'] / 100000000, 2)
                                    break
                        threshold = map_mc_to_threshold(market_cap)

                    futures.append(executor.submit(lbank_get_big_trades, symbol, base_url, threshold))

            for future in concurrent.futures.as_completed(futures):
                message_part = future.result()
                if message_part:
                    safe_send_message(chat_id, message_part)
                    time.sleep(1)

        # 定期清理历史记录，避免内存泄漏
        if len(lbank_his) > 10000:
            lbank_his.clear()

        time.sleep(60)
