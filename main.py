import concurrent.futures
import datetime
import io
import json
import os
import random
from datetime import timedelta, timezone

import matplotlib.pyplot as plt
import requests
from binance.um_futures import UMFutures
from dateutil.relativedelta import relativedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bithumb import is_on_alert, get_bithumb_token_list
from upbit import get_24h_volume, get_15m_upbit_volume, get_15m_upbit_volume_increase, get_upbit_token_list

um_futures_client = UMFutures()

# 为扫描任务创建单独的 session
binance_session = requests.Session()
binance_retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
binance_adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=binance_retry_strategy)
binance_session.mount("https://", binance_adapter)
binance_session.mount("http://", binance_adapter)
symbol1000 = ['XECUSDT', 'LUNCUSDT', 'PEPEUSDT', 'SHIBUSDT', 'BONKUSDT', 'SATSUSDT', 'RATSUSDT', 'FLOKIUSDT',
              '00MOGUSDT', '000MOGUSDT', 'MOGUSDT', 'CATUSDT', 'WHYUSDT', 'CHEEMSUSDT', 'XUSDT']


def binance_api_get(endpoint, params=None):
    # Binance API base URLs
    base_urls = [
        "https://api.binance.com",
        "https://api-gcp.binance.com",
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com",
        "https://api4.binance.com"
    ]

    # Randomly select a base URL
    base_url = random.choice(base_urls)
    url = f"{base_url}/{endpoint}"

    try:
        response = binance_session.get(url, params=params)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            return response.json()  # Return JSON response
        else:
            print(f"Failed to fetch data from {url}. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"Error making request to {url}: {e}")

    return None  # Return None if the request fails


def recommend(cir_df, rank=30, endpoint="api/v3/ticker/24hr"):
    recommend_list = []
    params = {}
    result = binance_api_get(endpoint, params)
    res = result
    result_future = um_futures_client.ticker_24hr_price_change(**params)
    res1 = result_future
    now_utc = datetime.datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=0.5)
    yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000

    # 检查 res 是否是列表，确保不是空列表
    if isinstance(res, list) and res and isinstance(res1, list) and res1:
        result_dict = {item['symbol'][4:] if item['symbol'].startswith("1000") else item['symbol']: item for item in
                       res}
        for item in res1:
            sym = item['symbol'][4:] if item['symbol'].startswith("1000") else item['symbol']
            if sym not in result_dict:
                result_dict[sym] = item
        result_list = list(result_dict.values())

        # 过滤
        fil_str_list = ['USDC', 'FDUSD', 'TUSDUSDT', 'USDP', 'EUR']

        filtered_tokens = [
            token for token in result_list
            if token['symbol'].endswith("USDT")
               and all(f not in token['symbol'] for f in fil_str_list)
               and token['count'] != 0
               and token['closeTime'] > yesterday_timestamp_utc
        ]

        # 按照 priceChangePercent 进行排序
        sorted_res = sorted(filtered_tokens, key=lambda x: float(x['priceChangePercent']), reverse=True)

        # 获取排序后的 symbol 列表
        usdt_symbols = [token['symbol'] for token in sorted_res]

        # 筛选出前15
        usdt_symbols_rise = usdt_symbols[:rank]

        additional_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        usdt_symbols_rise += additional_symbols
        # 去重
        unique_usdt_symbols_rise = set(usdt_symbols_rise)
        # 转换成列表
        usdt_symbols_rise = list(unique_usdt_symbols_rise)

        up24 = get_24h_volume(rank=20)
        up15 = get_15m_upbit_volume(rank=20)
        up_token = get_upbit_token_list()
        bithumb_token = get_bithumb_token_list()
        for symbol in usdt_symbols_rise:
            new_symbol = symbol[4:-4].lower() if symbol.startswith("1000") else symbol[:-4].lower()
            new_symbol = map_cmc_symbol(new_symbol)
            circle_supply = get_speicial_supply(new_symbol)
            if not circle_supply:
                circle_supply = get_circulating_supply(new_symbol, cir_df)
            if not circle_supply:
                continue
            flag = []
            try:
                v15_list = get_volume_increase_15(symbol)
                if v15_list[0] == 1:
                    flag.append([4, v15_list[1], v15_list[2]])
            except Exception as e:
                print(f'{symbol}:15m volume_increase error: {e}')

            try:

                p_len4, v_len4, vc_ratio = get_price_volume_increase(symbol, '4h', 5, circle_supply)
                if p_len4 >= 3 and v_len4 >= 2:
                    flag.append([1, p_len4, v_len4])
                if vc_ratio > 0.05:
                    flag.append([3, vc_ratio])
                # if taker_ratio4 > 0.6:
                #     flag.append([9, taker_ratio4])
                # if t_len4 >= 3:
                #     flag.append([11, t_len4])
            except Exception as e:
                print(f'{symbol}:4h error: {e}')

            # buy_spot = search_more_big_buy_spot(symbol)
            # buy_future = search_more_big_buy_future(symbol)
            # for i in range(4):
            #     if buy_spot[i] == 1 or buy_future == 1:
            #         flag.append([5, buy_spot, buy_future])
            #         break

            om_ratio = get_oi_mc_ratio(symbol, circle_supply)
            if om_ratio:
                if om_ratio > 0.5:
                    flag.append([13, om_ratio])

            # longshortRatio_rate1 = get_future_takerlongshortRatio(symbol, '30m')
            # longshortRatio_rate4 = get_future_takerlongshortRatio(symbol, '1h')
            # if longshortRatio_rate1:
            #     if longshortRatio_rate1 > 0.1:
            #         flag.append([7, longshortRatio_rate1])
            # if longshortRatio_rate4:
            #     if longshortRatio_rate4 > 0.1:
            #         flag.append([8, longshortRatio_rate4])

            # agg_spot = get_aggTrades_spot(symbol)
            # agg_future = get_aggTrades_future(symbol)
            # if len(agg_spot) > 0 or len(agg_future) > 0:
            #     flag.append([6, agg_spot, agg_future])

            oi_increase, oi_decrease = get_oi_increase(symbol)
            if oi_increase is None or oi_decrease is None:
                print(f"{symbol}获取持仓递增数据错误")
            else:
                if oi_increase >= 3:
                    flag.append([20, oi_increase, 1])
                elif oi_decrease >= 3:
                    flag.append([20, oi_decrease, 0])

            # oil = fetch_openInterest_diff(symbol, 0, 3)
            # if oil:
            #     if oil[2] >= 10:
            #         flag.append([14, oil[1], oil[2]])
            #     if oil[5] >= 10:
            #         flag.append([15, oil[4], oil[5]])
            # else:
            #     print(f"{symbol}获取持仓数据错误")

            if up24 and (symbol not in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']):
                for i, item in enumerate(up24):
                    if symbol[:-4] == item[0]:
                        flag.append([16, 20 - i])
            else:
                print(f"{symbol}获取up24h交易量数据错误")

            if up15 and (symbol not in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']):
                for i, item in enumerate(up15):
                    if symbol[:-4] == item[0]:
                        flag.append([17, 20 - i])
            else:
                print(f"{symbol}获取up15m交易量数据错误")

            if up_token and (symbol[:-4] in up_token):
                up15_list = get_15m_upbit_volume_increase(symbol[:-4])
                if up15_list and up15_list[0] == 1:
                    flag.append([18, up15_list[1]])

            if bithumb_token and (symbol[:-4] in bithumb_token):
                bithumb_alert = is_on_alert(symbol[:-4])
                if bithumb_alert and bithumb_alert[0] == 1:
                    flag.append([19, bithumb_alert[1]])

            if len(flag) == 0:
                continue
            else:
                price = get_latest_price(symbol)
                recommend_list.append({symbol[:-4]: [price, flag]})
        return recommend_list
    else:
        print("无数据或数据格式不正确")


def max_increasing_length(data, is_volume=0):
    length = 0

    for i in range(len(data) - 1, 0, -1):
        if data[i] > data[i - 1]:  # 如果当前元素大于前一个元素，则降序序列长度 +1
            length += 1
        elif i == len(data) - 1:
            continue
        else:
            break  # 一旦不满足降序条件，退出循环

    return length if not is_volume else length + 1


def get_price_volume_increase(symbol, interval, limit, circle_supply):
    try:
        data = get_k_lines(symbol, interval, limit)

        volume_list = []
        endprice_list = []
        taker_list = []

        # 先看1h/4h红绿绿以及绿绿绿趋势,以及交易量趋势
        for l in data:
            endprice = float(l[4])
            vol = float(l[7])
            taker_vol = float(l[10])

            endprice_list.append(endprice)
            volume_list.append(vol)
            if vol > 0:
                taker_ratio = taker_vol / vol
                taker_list.append(taker_ratio)
            else:
                taker_list.append(0)

        p_len = max_increasing_length(endprice_list)
        v_len = max_increasing_length(volume_list, is_volume=1)
        # t_len = max_increasing_length(taker_list)

        # 再看交易量占比
        flag = -2 if volume_list[-2] > volume_list[-1] else -1
        volume = volume_list[flag]
        price = endprice_list[flag]
        cmc = circle_supply * price
        vc_ratio = round(float(volume / cmc), 2)

        # # 看主动成交额占比
        # taker_vol0 = float(data[0][10])
        # vol0 = float(data[0][7])
        # taker_ratio = round(taker_vol0 / vol0, 2)

        return p_len, v_len, vc_ratio
    except Exception as e:
        data = get_k_lines_future(symbol, interval, limit)

        volume_list = []
        endprice_list = []
        taker_list = []

        # 先看1h/4h红绿绿以及绿绿绿趋势,以及交易量趋势
        for l in data:
            endprice = float(l[4])
            vol = float(l[7])
            taker_vol = float(l[10])

            endprice_list.append(endprice)
            volume_list.append(vol)
            if vol > 0:
                taker_ratio = taker_vol / vol
                taker_list.append(taker_ratio)
            else:
                taker_list.append(0)

        p_len = max_increasing_length(endprice_list)
        v_len = max_increasing_length(volume_list, is_volume=1)
        # t_len = max_increasing_length(taker_list)

        # 再看交易量占比
        flag = -2 if volume_list[-2] > volume_list[-1] else -1
        volume = volume_list[flag]
        price = endprice_list[flag]
        cmc = circle_supply * price
        vc_ratio = round(float(volume / cmc), 2)

        # # 看主动成交额占比
        # taker_vol0 = float(data[0][10])
        # vol0 = float(data[0][7])
        # taker_ratio = round(taker_vol0 / vol0, 2)

        return p_len, v_len, vc_ratio


def get_volume_increase_15(symbol):
    try:
        data15 = get_k_lines(symbol, '15m', 2)
        # 再看15min内是否有交易量激增
        v_now = float(data15[1][7])
        v_past = float(data15[0][7])
        v_ratio = round(float(v_now / v_past), 2)
        if v_ratio >= 3:
            if data15[1][4] > data15[0][4]:
                v15_list = [1, 1, v_ratio]
            else:
                v15_list = [1, 0, v_ratio]
        else:
            v15_list = [0, 0, v_ratio]
        return v15_list
    except Exception as e:
        data15 = get_k_lines_future(symbol, '15m', 2)
        # 再看15min内是否有交易量激增
        v_now = float(data15[1][7])
        v_past = float(data15[0][7])
        v_ratio = round(float(v_now / v_past), 2)
        if v_ratio >= 3:
            if data15[1][4] > data15[0][4]:
                v15_list = [1, 1, v_ratio]
            else:
                v15_list = [1, 0, v_ratio]
        else:
            v15_list = [0, 0, v_ratio]
        return v15_list


def get_k_lines(symbol, interval, limit, endpoint="api/v3/klines"):
    para = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    data = binance_api_get(endpoint, para)
    return data


def get_k_lines_future(symbol, interval, limit):
    para = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    data = um_futures_client.klines(**para)
    return data


def get_latest_price(symbol, endpoint='api/v3/ticker/price'):
    try:
        para = {
            'symbol': symbol
        }
        price = float(binance_api_get(endpoint, para)['price'])
        if symbol.startswith("1000") or symbol in symbol1000:
            return price * 1000
        else:
            return price
    except Exception as e:
        para = {
            'symbol': symbol
        }
        price = float(um_futures_client.ticker_price(**para)['price'])
        if symbol.startswith("1000") or symbol in symbol1000:
            return price * 1000
        else:
            return price


# def get_window_chg(symbol, windowSize, endpoint="api/v3/ticker"):
#     para = {
#         'symbol': symbol,
#         'windowSize': windowSize
#     }
#     data = binance_api_get(endpoint, para)
#     return data


def get_circulating_supply(symbol, df):
    result = df[df['symbol'] == symbol]
    if not result.empty:
        value = int(result['circle_supply'].iloc[0])
    else:
        print(f"{symbol}没找到对应流通量")
        return None
    return value


def check_time_4():
    # 获取当前时间
    current_time = datetime.datetime.now()
    # 获取当前小时和分钟
    current_hour = current_time.hour
    current_minute = current_time.minute

    # 定义我们感兴趣的小时
    target_hours = [2, 6, 10, 16, 18, 22]

    # 检查当前小时是否在目标小时内，并且分钟在0到5之间
    if current_hour in target_hours and 0 <= current_minute <= 10:
        return True
    else:
        return False


def check_time_1():
    # 获取当前时间
    current_time = datetime.datetime.now()
    # 获取当前小时和分钟
    current_hour = current_time.hour
    current_minute = current_time.minute

    # 定义我们感兴趣的小时
    target_hours = list(range(25))

    # 检查当前小时是否在目标小时内，并且分钟在0到5之间
    if current_hour in target_hours and 0 <= current_minute <= 5:
        return True
    else:
        return False


def check_time_15():
    # 获取当前时间
    current_time = datetime.datetime.now()
    # 获取当前小时和分钟
    current_minute = current_time.minute

    if 0 <= current_minute % 15 <= 1:
        return True
    else:
        return False


def get_best_bid(symbol, endpoint='api/v3/ticker/bookTicker'):
    para = {
        'symbol': symbol
    }
    data = binance_api_get(endpoint, para)
    return data


def get_latest_trade(symbol, endpoint='api/v3/aggTrades'):
    para = {
        'symbol': symbol
    }
    data = binance_api_get(endpoint, para)
    return data


def get_future_volume(symbol, period, endpoint='futures/data/openInterestHist'):
    try:
        if symbol in symbol1000:
            symbol = '1000' + symbol
        para = {
            'symbol': symbol,
            'period': period
        }
        data = binance_api_get(endpoint, para)
        return data
    except Exception as e:
        symbol = '1000' + symbol
        para = {
            'symbol': symbol,
            'period': period
        }
        data = binance_api_get(endpoint, para)
        return data


def search_more_big_buy_spot(symbol, order_value=None, limit=5000, endpoint='api/v3/depth',
                             bpr=0.1, spr=0.1):
    if order_value is None:
        order_value = [10000, 100000, 500000, 1000000]
    try:
        para = {
            'symbol': symbol,
            'limit': limit
        }
        data = binance_api_get(endpoint, para)
        sp = float(get_latest_price(symbol))

        buy = [0, 0, 0, 0]
        for l in data['bids']:
            p = float(l[0])
            v = int(p * float(l[1]))
            for i, ov in enumerate(order_value):
                if i == len(order_value) - 1:
                    if sp * (1 - bpr) <= p and v >= ov:
                        buy[i] += v
                else:
                    if sp * (1 - bpr) <= p and order_value[i + 1] > v >= ov:
                        buy[i] += v

        sell = [0, 0, 0, 0]
        for l in data['asks']:
            p = float(l[0])
            v = int(p * float(l[1]))
            for i, ov in enumerate(order_value):
                if i == len(order_value) - 1:
                    if p <= sp * (1 + spr) and v >= ov:
                        sell[i] += v
                else:
                    if p <= sp * (1 + spr) and order_value[i + 1] > v >= ov:
                        sell[i] += v

        res = []
        for i in range(len(order_value)):
            if buy[i] > sell[i]:
                res.append(1)
            else:
                res.append(0)
        return res
    except Exception as e:
        return [0, 0, 0, 0]


def search_more_big_buy_future(symbol, order_value=None, limit=1000, bpr=0.1, spr=0.1):
    if symbol in symbol1000:
        symbol = '1000' + symbol

    if order_value is None:
        order_value = [10000, 100000, 500000, 1000000]
    try:
        para = {
            'symbol': symbol,
            'limit': limit
        }
        data = um_futures_client.depth(**para)
        ppara = {
            'symbol': symbol
        }
        fp = float(um_futures_client.ticker_price(**ppara)['price'])

        buy = [0, 0, 0, 0]
        for l in data['bids']:
            p = float(l[0])
            v = int(p * float(l[1]))
            for i, ov in enumerate(order_value):
                if i == len(order_value) - 1:
                    if fp * (1 - bpr) <= p and v >= ov:
                        buy[i] += v
                else:
                    if fp * (1 - bpr) <= p and order_value[i + 1] > v >= ov:
                        buy[i] += v

        sell = [0, 0, 0, 0]
        for l in data['asks']:
            p = float(l[0])
            v = int(p * float(l[1]))
            for i, ov in enumerate(order_value):
                if i == len(order_value) - 1:
                    if p <= fp * (1 + spr) and v >= ov:
                        sell[i] += v
                else:
                    if p <= fp * (1 + spr) and order_value[i + 1] > v >= ov:
                        sell[i] += v

        res = []
        for i in range(len(order_value)):
            if buy[i] > sell[i]:
                res.append(1)
            else:
                res.append(0)
        return res
    except Exception as e:
        return [0, 0, 0, 0]


def get_oi_mc_ratio(symbol, supply):
    try:
        openInterest = um_futures_client.open_interest(symbol)
        if not openInterest:
            return None
        else:
            oi_value = float(openInterest['openInterest'])
            return oi_value / supply
    except Exception as e:
        print(f"{symbol} get_oi_mc_ratio error:{e}")
        return None


def get_aggTrades_spot(symbol, endpoint='api/v3/aggTrades', target=100000):
    para = {
        'symbol': symbol
    }
    data = binance_api_get(endpoint, para)

    res = []
    for d in data:
        v = float(d['p']) * float(d['q'])
        if v >= target:
            res.append(v)
    return res


def get_aggTrades_future(symbol, target=100000):
    try:
        if symbol in symbol1000:
            symbol = '1000' + symbol
        para = {
            'symbol': symbol
        }
        data = um_futures_client.agg_trades(**para)

        res = []
        for d in data:
            v = float(d['p']) * float(d['q'])
            if v >= target:
                res.append(v)
        return res
    except Exception as e:
        return []


def scan_big_order_spot(symbol, limit=1000, endpoint='api/v3/aggTrades', target=100000):
    try:
        buy = []
        sell = []

        para = {
            'symbol': symbol,
            'limit': limit
        }
        data = binance_api_get(endpoint, para)
        for d in data:
            p = float(d['p'])
            v = p * float(d['q'])
            if v >= target:
                if d['m']:
                    sell.append([v, d['T'], p])
                else:
                    buy.append([v, d['T'], p])
        return buy, sell
    except Exception as e:
        print(f"{symbol}big order spot error:{e}")
        return [], []


def scan_big_order_future(symbol, limit=1000, target=100000):
    try:
        buy = []
        sell = []

        if symbol in symbol1000:
            symbol = '1000' + symbol
        para = {
            'symbol': symbol,
            'limit': limit
        }
        data = um_futures_client.agg_trades(**para)

        for d in data:
            p = float(d['p'])
            v = p * float(d['q'])
            if v >= target:
                if d['m']:
                    sell.append([v, d['T'], p])
                else:
                    buy.append([v, d['T'], p])
        return buy, sell
    except Exception as e:
        print(f"{symbol}big order future error:{e}")
        return [], []


def map_mc_to_threshold(mc):
    if mc < 1:
        return 50000
    elif 1 <= mc < 2:
        return 60000
    elif 2 <= mc < 5:
        return 80000
    elif 5 <= mc < 10:
        return 100000
    else:
        return 200000


def scan_big_order(record, endpoint='api/v3/ticker/24hr', rank=12, add=None):
    thresholds = {'BTC': 2500000, 'ETH': 1000000, 'SOL': 1000000, 'DOGE': 500000, 'XRP': 500000}
    recommend_list = []
    params = {}
    result = binance_api_get(endpoint, params)
    result_future = um_futures_client.ticker_24hr_price_change(**params)
    res = result
    res1 = result_future
    now_utc = datetime.datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=0.5)
    yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000

    # 假设 res 是一个列表，每个元素是一个字典，包含 'symbol' 和 'priceChangePercent' 字段

    # 检查 res 是否是列表，确保不是空列表
    if isinstance(res, list) and res and isinstance(res1, list) and res1:
        result_dict = {item['symbol'][4:] if item['symbol'].startswith("1000") else item['symbol']: item for item in
                       res}
        for item in res1:
            sym = item['symbol'][4:] if item['symbol'].startswith("1000") else item['symbol']
            if sym not in result_dict:
                result_dict[sym] = item
        result_list = list(result_dict.values())
        # 过滤
        fil_str_list = ['USDC', 'FDUSD', 'TUSDUSDT', 'USDP', 'EUR']

        filtered_tokens = [
            token for token in result_list
            if token['symbol'].endswith("USDT")
               and all(f not in token['symbol'] for f in fil_str_list)
               and token['count'] != 0
               and token['closeTime'] > yesterday_timestamp_utc
        ]

        # 按照 priceChangePercent 进行排序
        sorted_res = sorted(filtered_tokens, key=lambda x: float(x['priceChangePercent']), reverse=True)

        # 获取排序后的 symbol 列表
        usdt_symbols = [token['symbol'] for token in sorted_res]

        # 筛选出前15
        usdt_symbols_rise = usdt_symbols[:rank]
        # 增加额外的币种
        usdt_symbols_rise += ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        if add:
            usdt_symbols_rise += add
        # 去重
        usdt_symbols_rise = list(set(usdt_symbols_rise))

        for symbol in usdt_symbols_rise:
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
            buy_spot, sell_spot = scan_big_order_spot(symbol, target=threshold)
            buy_future, sell_future = scan_big_order_future(symbol, target=threshold)
            spot = []
            future = []
            if len(buy_spot) > 0:
                for v in buy_spot:
                    if v[1] not in record:
                        spot.append([1, v[0], v[2], v[1]])
                        record.add(v[1])
            if len(sell_spot) > 0:
                for v in sell_spot:
                    if v[1] not in record:
                        spot.append([0, v[0], v[2], v[1]])
                        record.add(v[1])
            if len(buy_future) > 0:
                for v in buy_future:
                    if v[1] not in record:
                        future.append([1, v[0], v[2], v[1]])
                        record.add(v[1])
            if len(sell_future) > 0:
                for v in sell_future:
                    if v[1] not in record:
                        future.append([0, v[0], v[2], v[1]])
                        record.add(v[1])
            if len(spot) > 0 or len(future) > 0:
                recommend_list.append({symbol[:-4]: [spot, future]})
    return recommend_list


def get_future_takerlongshortRatio(symbol, interval):
    try:
        if symbol in symbol1000:
            symbol = '1000' + symbol

        para1 = {
            'symbol': symbol,
            'period': interval,
            'limit': 2
        }
        data = um_futures_client.taker_long_short_ratio(**para1)

        ratio_rate = (float(data[0]['buySellRatio']) - float(data[1]['buySellRatio'])) / float(
            data[1]['buySellRatio'])

        return ratio_rate
    except Exception as e:
        return None


def fetch_taker_data_future(symbol, p_chg, interval, limit):
    """
    获取每个 symbol 的净成交量数据
    :param symbol: 交易对
    :param interval: 时间间隔
    :return: 返回 symbol 和净成交量（如果获取失败返回 None）
    """
    para = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    k_line = um_futures_client.klines(**para)
    # 有可能有些币没有合约~
    if not k_line:
        return None
    else:
        net = 0
        for k in k_line:
            price = float(k[4])
            v = float(k[5])
            taker = float(k[9])
            maker = v - taker
            net_volume = (taker - maker) * price
            net += net_volume
        return [symbol[:-4], round(net, 2), p_chg]


def get_net_volume_rank_future(interval, rank=10, reverse=True):
    """
    获取所有 symbol 的净成交量排名，并行请求 API
    :param interval: 时间间隔
    :param rank: 返回排名数量    new_interval, limit = parse_interval_to_minutes(interval)
    :param reverse: 排序方式，默认为从高到低
    :return: 排名前的 symbol 列表
    """
    data = um_futures_client.ticker_24hr_price_change()
    # 获取前一天的时间戳
    now_utc = datetime.datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)
    yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
    symbols = [[v['symbol'], round(float(v['priceChangePercent']), 2)] for v in data if
               v['symbol'].endswith('USDT') and 'USDC' not in v['symbol'] and 'FDUSD' not in v['symbol'] and v[
                   'count'] != 0 and v['closeTime'] > yesterday_timestamp_utc]

    net_list = []
    new_interval, limit = parse_interval_to_minutes(interval)

    # 使用 ThreadPoolExecutor 进行并行 API 请求
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有的 API 请求，并行运行 fetch_taker_data 函数
        futures = [executor.submit(fetch_taker_data_future, symbol[0], symbol[1], new_interval, limit) for symbol in
                   symbols]

        # 等待所有任务完成，并收集结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                net_list.append(result)

    # 按净成交量进行排序
    sorted_list = sorted(net_list, key=lambda x: x[1], reverse=reverse)[:rank]
    return sorted_list


def fetch_taker_data_spot(symbol, p_chg, interval, limit):
    """
    获取每个 symbol 的净成交量数据
    :param symbol: 交易对
    :param interval: 时间间隔
    :return: 返回 symbol 和净成交量（如果获取失败返回 None）
    """
    k_line = get_k_lines(symbol, interval, limit)
    net = 0
    for k in k_line:
        price = float(k[4])
        v = float(k[5])
        taker = float(k[9])
        maker = v - taker
        net_volume = (taker - maker) * price
        net += net_volume
    return [symbol[:-4], round(net, 2), p_chg]


def get_net_volume_rank_spot(interval, rank=10, reverse=True):
    """
    获取所有 symbol 的净成交量排名，并行请求 API
    :param interval: 时间间隔
    :param rank: 返回排名数量
    :param reverse: 排序方式，默认为从高到低
    :return: 排名前的 symbol 列表
    """
    endpoint = "api/v3/ticker/24hr"
    params = {}
    data = binance_api_get(endpoint, params)
    now_utc = datetime.datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)
    yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
    symbols = [[v['symbol'], round(float(v['priceChangePercent']), 2)] for v in data if
               v['symbol'].endswith('USDT') and 'USDC' not in v['symbol'] and 'FDUSD' not in v['symbol'] and v[
                   'count'] != 0 and float(v['bidPrice']) != 0 and float(v['askPrice']) != 0 and v[
                   'closeTime'] > yesterday_timestamp_utc]

    net_list = []

    new_interval, limit = parse_interval_to_minutes(interval)

    # 使用 ThreadPoolExecutor 进行并行 API 请求
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有的 API 请求，并行运行 fetch_taker_data 函数
        futures = [executor.submit(fetch_taker_data_spot, symbol[0], symbol[1], new_interval, limit) for symbol in
                   symbols]

        # 等待所有任务完成，并收集结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                net_list.append(result)

    # 按净成交量进行排序
    sorted_list = sorted(net_list, key=lambda x: x[1], reverse=reverse)[:rank]
    return sorted_list


def parse_interval_to_minutes(interval):
    """
    将时间间隔解析为对应的分钟数或5分钟间隔数
    :param interval: 输入的时间间隔（如 '4h', '1h', '15m', '1d'）
    :return: 返回对应的分钟数，或者若是天单位，返回多少个5分钟间隔
    """
    if interval.endswith('h'):
        # 如果时间间隔以 'h' 结尾，转换为小时，然后乘以 60
        return '1m', int(interval[:-1]) * 60
    elif interval.endswith('m'):
        # 如果时间间隔以 'm' 结尾，直接转换为分钟
        return '1m', int(interval[:-1])
    elif interval.endswith('d'):
        # 如果时间间隔以 'd' 结尾，转换为天并计算有多少个5分钟间隔
        minutes = int(interval[:-1]) * 1440  # 1天 = 1440分钟
        return '5m', minutes // 5  # 计算有多少个5分钟间隔
    else:
        raise ValueError("无效的时间间隔格式！请使用 'h', 'm', 或 'd' 作为单位。")


def parse_interval_to_5minutes(interval):
    # 获取时间的数值和单位
    unit = interval[-1]  # 最后一个字符是单位
    value = float(interval[:-1])  # 前面的部分是数值

    # 将单位转换为分钟
    if unit == 'm':
        total_minutes = value
    elif unit == 'h':
        total_minutes = value * 60
    elif unit == 'd':
        total_minutes = value * 24 * 60
    else:
        raise ValueError("Unsupported time unit. Use 'm' for minutes, 'h' for hours, or 'd' for days.")

    # 计算有多少个5分钟
    return int(total_minutes // 5)


def fetch_openInterest(symbol, p_chg, limit):
    para = {
        'symbol': symbol,
        'period': '5m',
        'limit': limit
    }
    openInterest = um_futures_client.open_interest_hist(**para)
    if not openInterest:
        return None
    else:
        openInterest = openInterest[0]
        sumOpenInterestValue = float(openInterest['sumOpenInterestValue'])
        ls_ratio = um_futures_client.top_long_short_position_ratio(**para)[0]
        delta_openInterest = (float(ls_ratio['longAccount']) - float(ls_ratio['shortAccount'])) * sumOpenInterestValue
        return [symbol[:-4], round(delta_openInterest, 2), p_chg, sumOpenInterestValue]


def get_openInterest_rank(interval, rank=10, reverse=True):
    data = um_futures_client.ticker_24hr_price_change()
    # 获取前一天的时间戳
    now_utc = datetime.datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)
    yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
    symbols = [[v['symbol'], round(float(v['priceChangePercent']), 2)] for v in data if
               v['symbol'].endswith('USDT') and 'USDC' not in v['symbol'] and 'FDUSD' not in v['symbol'] and v[
                   'count'] != 0 and v['closeTime'] > yesterday_timestamp_utc]

    delta_list = []

    limit = parse_interval_to_5minutes(interval)

    # 使用 ThreadPoolExecutor 进行并行 API 请求
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有的 API 请求，并行运行 fetch_taker_data 函数
        futures = [executor.submit(fetch_openInterest, symbol[0], symbol[1], limit) for symbol in symbols]

        # 等待所有任务完成，并收集结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                delta_list.append(result)

    # 按净持仓量进行排序
    sorted_list_net = sorted(delta_list, key=lambda x: x[1], reverse=reverse)[:rank]
    sorted_list_all = sorted(delta_list, key=lambda x: x[3], reverse=reverse)[:rank]
    return sorted_list_net, sorted_list_all


def fetch_openInterest_diff(symbol, p_chg, limit):
    if symbol in symbol1000:
        symbol = "1000" + symbol
    para = {
        'symbol': symbol,
        'period': '5m',
        'limit': limit
    }
    openInterest = um_futures_client.open_interest_hist(**para)
    if not openInterest:
        return None
    else:
        oi_before = openInterest[0]
        oi_now = openInterest[-1]
        sumOpenInterestValue_before = float(oi_before['sumOpenInterest'])
        sumOpenInterestValue_now = float(oi_now['sumOpenInterest'])
        ls_ratio_before = um_futures_client.top_long_short_position_ratio(**para)[0]
        ls_ratio_now = um_futures_client.top_long_short_position_ratio(**para)[-1]
        delta_openInterest_before = (float(ls_ratio_before['longAccount']) - float(
            ls_ratio_before['shortAccount'])) * sumOpenInterestValue_before
        delta_openInterest_now = (float(ls_ratio_now['longAccount']) - float(
            ls_ratio_now['shortAccount'])) * sumOpenInterestValue_now
        diff = round(delta_openInterest_now - delta_openInterest_before, 2)
        diff_total = round(sumOpenInterestValue_now - sumOpenInterestValue_before, 2)
        delta_openInterest_before = delta_openInterest_before if delta_openInterest_before != 0 else 1e-10
        sumopenInterest_before = sumOpenInterestValue_before if sumOpenInterestValue_before != 0 else 1e-10
        diff_ratio = round((diff / abs(delta_openInterest_before)) * 100, 2)
        diff_ratio_total = round((diff_total / abs(sumopenInterest_before)) * 100, 2)
        return [symbol[:-4], diff, diff_ratio, p_chg, diff_total, diff_ratio_total]


def get_openInterest_diff_rank(interval, rank=10, reverse=True):
    data = um_futures_client.ticker_24hr_price_change()
    # 获取前一天的时间戳
    now_utc = datetime.datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)
    yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
    symbols = [[v['symbol'], round(float(v['priceChangePercent']), 2)] for v in data if
               v['symbol'].endswith('USDT') and 'USDC' not in v['symbol'] and 'FDUSD' not in v['symbol'] and v[
                   'count'] != 0 and v['closeTime'] > yesterday_timestamp_utc]

    delta_list = []

    limit = parse_interval_to_5minutes(interval)

    # 使用 ThreadPoolExecutor 进行并行 API 请求
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有的 API 请求，并行运行 fetch_taker_data 函数
        futures = [executor.submit(fetch_openInterest_diff, symbol[0], symbol[1], limit) for symbol in symbols]

        # 等待所有任务完成，并收集结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                delta_list.append(result)

    # 按净持仓量进行排序
    sorted_list_net = sorted(delta_list, key=lambda x: x[2], reverse=reverse)[:rank]
    sorted_list_all = sorted(delta_list, key=lambda x: x[5], reverse=reverse)[:rank]
    return sorted_list_net, sorted_list_all


def get_bi_openInterest_diff_rank(interval, rank=10):
    data = um_futures_client.ticker_24hr_price_change()
    # 获取前一天的时间戳
    now_utc = datetime.datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)
    yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
    symbols = [[v['symbol'], round(float(v['priceChangePercent']), 2)] for v in data if
               v['symbol'].endswith('USDT') and 'USDC' not in v['symbol'] and 'FDUSD' not in v['symbol'] and v[
                   'count'] != 0 and v['closeTime'] > yesterday_timestamp_utc]

    delta_list = []

    limit = parse_interval_to_5minutes(interval)

    # 使用 ThreadPoolExecutor 进行并行 API 请求
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有的 API 请求，并行运行 fetch_taker_data 函数
        futures = [executor.submit(fetch_openInterest_diff, symbol[0], symbol[1], limit) for symbol in symbols]

        # 等待所有任务完成，并收集结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                delta_list.append(result)

    # 按净持仓量进行排序
    sorted_list_net_d = sorted(delta_list, key=lambda x: x[2], reverse=True)[:rank]
    sorted_list_all_d = sorted(delta_list, key=lambda x: x[5], reverse=True)[:rank]
    sorted_list_net_a = sorted(delta_list, key=lambda x: x[2], reverse=False)[:rank]
    sorted_list_all_a = sorted(delta_list, key=lambda x: x[5], reverse=False)[:rank]
    return sorted_list_net_d, sorted_list_all_d, sorted_list_net_a, sorted_list_all_a


def fetch_long_short_switch(symbol, pchg, limit):
    if symbol in symbol1000:
        symbol = "1000" + symbol
    para = {
        'symbol': symbol,
        'period': '5m',
        'limit': limit
    }
    openInterest = um_futures_client.open_interest_hist(**para)
    if not openInterest:
        print(f"{symbol} fetch_long_short_switch error")
        return None
    else:
        oi_before = openInterest[0]
        oi_now = openInterest[-1]
        oi_value_before = float(oi_before['sumOpenInterestValue'])
        oi_value_now = float(oi_now['sumOpenInterestValue'])
        oi_before = float(oi_before['sumOpenInterest'])
        oi_now = float(oi_now['sumOpenInterest'])
        oi_value_switch_ratio = (oi_value_now - oi_value_before) / oi_value_before
        oi_switch_ratio = (oi_now - oi_before) / oi_before
        if oi_switch_ratio == 0 and oi_value_switch_ratio == 0:
            switch_index = [-1, 0]
        elif oi_switch_ratio <= 0 and oi_value_switch_ratio >= 0:
            # 持仓量减少，但是持仓价值增加(多转空)
            oi_switch_ratio = 1e-10 if oi_switch_ratio == 0 else oi_switch_ratio
            switch_index = [0, 100 * round(abs(oi_value_switch_ratio / oi_switch_ratio), 2)]
        elif oi_switch_ratio >= 0 and oi_value_switch_ratio <= 0:
            # 持仓量增加，但是持仓量减少(空转多)
            oi_value_switch_ratio = 1e-10 if oi_value_switch_ratio == 0 else oi_value_switch_ratio
            switch_index = [1, 100 * round(abs(oi_switch_ratio / oi_value_switch_ratio), 2)]
        else:
            switch_index = [-1, 0]

        switch_num_0 = 0
        switch_num_1 = 0
        for i in range(len(openInterest) - 1, -1, -1):
            if float(openInterest[i]['sumOpenInterest']) < float(openInterest[i - 1]['sumOpenInterest']) and float(
                    openInterest[i]['sumOpenInterestValue']) > float(openInterest[i - 1]['sumOpenInterestValue']):
                # 持仓量连续降低并且持仓价值连续增高
                switch_num_0 += 1
            else:
                break
        for i in range(len(openInterest) - 1, -1, -1):
            if float(openInterest[i]['sumOpenInterest']) > float(openInterest[i - 1]['sumOpenInterest']) and float(
                    openInterest[i]['sumOpenInterestValue']) < float(openInterest[i - 1]['sumOpenInterestValue']):
                # 持仓量连续降低并且持仓价值连续增高
                switch_num_1 += 1
            else:
                break
        if switch_num_0 > 0:
            switch_num = [0, switch_num_0]
        elif switch_num_1 > 0:
            switch_num = [1, switch_num_1]
        else:
            switch_num = [-1, -1]
        return [symbol[:-4], switch_index, switch_num, pchg]


def get_long_short_switch_point(interval, rank=10, reverse=True):
    data = um_futures_client.ticker_24hr_price_change()
    # 获取前一天的时间戳
    now_utc = datetime.datetime.now(timezone.utc)
    yesterday_utc = now_utc - timedelta(days=1)
    yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
    symbols = [[v['symbol'], round(float(v['priceChangePercent']), 2)] for v in data if
               v['symbol'].endswith('USDT') and 'USDC' not in v['symbol'] and 'FDUSD' not in v['symbol'] and v[
                   'count'] != 0 and v['closeTime'] > yesterday_timestamp_utc]

    delta_list = []

    limit = parse_interval_to_5minutes(interval)

    # 使用 ThreadPoolExecutor 进行并行 API 请求
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有的 API 请求，并行运行 fetch_taker_data 函数
        futures = [executor.submit(fetch_long_short_switch, symbol[0], symbol[1], limit) for symbol in symbols]

        # 等待所有任务完成，并收集结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                delta_list.append(result)

    filtered_list_0 = [x for x in delta_list if x[1][0] == 0 and x[2][0] == 0]
    sorted_list_0 = sorted(filtered_list_0, key=lambda x: (x[2][1], x[1][1]), reverse=reverse)[:rank]
    filtered_list_1 = [x for x in delta_list if x[1][0] == 1 and x[2][0] == 1]
    sorted_list_1 = sorted(filtered_list_1, key=lambda x: (x[2][1], x[1][1]), reverse=reverse)[:rank]
    return sorted_list_0, sorted_list_1


def get_symbol_open_interest(symbol):
    interval_list = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "16h", "20h", "1d", "1.5d"]
    res = []
    oi_newest = um_futures_client.open_interest(symbol)
    if not oi_newest:
        return None
    else:
        oi0 = float(oi_newest['openInterest'])
        res.append(["0m", "-", round(oi0, 2)])
    for interval in interval_list:
        limit = parse_interval_to_5minutes(interval)
        para = {
            'symbol': symbol,
            'period': '5m',
            'limit': limit
        }
        openInterest = um_futures_client.open_interest_hist(**para)
        if not openInterest:
            return None
        else:
            openInterest = openInterest[0]
            sumOpenInterestValue = float(openInterest['sumOpenInterest'])
            ls_ratio = um_futures_client.top_long_short_position_ratio(**para)[0]
            delta_openInterest = (float(ls_ratio['longAccount']) - float(
                ls_ratio['shortAccount'])) * sumOpenInterestValue
            res.append([interval, round(delta_openInterest, 2), round(sumOpenInterestValue, 2)])
    return res


def get_token_info(symbol, data):
    # 查找符号匹配的代币
    for token in data['data']:
        if token['symbol'].lower() == symbol.lower():
            total_supply = token['total_supply']
            circulating_supply = token['circulating_supply']
            circulating_rate = round(circulating_supply / total_supply * 100, 2)
            infinite_supply = token['infinite_supply']
            tags = token['tags']
            market_cap = round(token['quote']['USD']['market_cap'] / 100000000, 2)
            return market_cap, circulating_rate, infinite_supply, tags
    print(f"Symbol {symbol} not found in the data.")


def get_binance_spot_info(symbol):
    try:
        k = get_k_lines(symbol, '3d', 1000)
        # 获取前一天的时间戳
        now_utc = datetime.datetime.now(timezone.utc)
        yesterday_utc = now_utc - timedelta(days=1)
        yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
        if k[len(k) - 1][6] < yesterday_timestamp_utc:
            return f"\n🚫️*现货已下线*\n"

        time = k[0][0]
        timestamp_in_seconds = time / 1000

        # 转换为 datetime 对象
        utc_time = datetime.datetime.utcfromtimestamp(timestamp_in_seconds)

        # 获取当前时区的时间
        local_time = utc_time.astimezone()

        # 使用 strftime 来格式化输出
        formatted_local_time = local_time.strftime("%Y-%m-%d %H:%M")
        res = f"\n📅*现货*上币安时间：{formatted_local_time}\t"

        # 获取当前日期
        current_date = datetime.datetime.utcnow()

        # 计算两个日期的差异
        difference = relativedelta(current_date, utc_time)

        # 输出结果
        res += f"⏳已上线： {abs(difference.years)}年{abs(difference.months)}个月{abs(difference.days)}天\n"
        return res
    except Exception as e:
        return None


def get_binance_spot_future(symbol):
    try:
        para = {
            'symbol': symbol,
            'interval': '3d',
            'limit': 1000
        }
        k = um_futures_client.klines(**para)

        if k[len(k) - 1][8] == 0:
            return f"🚫️*合约已下线*\n"

        data = k[0][0]
        # 将时间戳从毫秒转换为秒
        timestamp_in_seconds = data / 1000

        # 转换为 datetime 对象
        utc_time = datetime.datetime.utcfromtimestamp(timestamp_in_seconds)

        # 获取当前时区的时间
        local_time = utc_time.astimezone()

        # 使用 strftime 来格式化输出
        formatted_local_time = local_time.strftime("%Y-%m-%d %H:%M")
        res = f"📅*合约*上币安时间：{formatted_local_time}\t"

        # 获取当前日期
        current_date = datetime.datetime.utcnow()

        # 计算两个日期的差异
        difference = relativedelta(current_date, utc_time)

        # 输出结果
        res += f"⏳已上线： {abs(difference.years)}年{abs(difference.months)}个月{abs(difference.days)}天\n"
        return res
    except Exception as e:
        return None


def get_symbol_info(symbol, data):
    res = f"💎*symbol*：`{symbol.upper()}`\n"
    market_cap, circulating_rate, infinite_supply, tags = get_token_info(symbol, data)
    res += f"💵*市值*：{market_cap}亿\n"
    res += f"🔄*流通率*：{circulating_rate}%\n"
    z = "是" if infinite_supply else "否"
    res += f"⚠️*增发*：{z}\n"

    keywords = ['-portfolio', '-ecosystem', '-estate', 'store-of-value', 'state-channel', 'sha-256',
                'cmc-crypto-awards', '-chain', '-ecosytem', '-capital']
    filtered_tags = [item for item in tags if not any(keyword in item for keyword in keywords)]
    res += f"🏷️*标签*：{str(filtered_tags)}\n"

    spot1 = get_binance_spot_info(symbol.upper() + 'USDT')
    spot2 = get_binance_spot_info("1000" + symbol.upper() + 'USDT')
    res += spot1 if spot1 else spot2 if spot2 else "\n🙅‍️未上币安现货\n"
    future1 = get_binance_spot_future(symbol.upper() + 'USDT')
    future2 = get_binance_spot_future("1000" + symbol.upper() + 'USDT')
    res += future1 if future1 else future2 if future2 else "🙅‍️未上币安期货\n"
    return res


def token_spot_future_delta(endpoint="api/v3/ticker/24hr"):
    params = {}
    spot = binance_api_get(endpoint, params)
    future = um_futures_client.ticker_24hr_price_change(**params)

    if isinstance(spot, list) and spot and isinstance(future, list) and future:
        # 过滤出包含 "USDT" 的币种
        symbols_spot = set(
            [token['symbol'][4:-4] if token['symbol'].startswith('1000') else token['symbol'][:-4] for token in spot
             if
             token['symbol'].endswith('USDT') and 'USDC' not in token['symbol'] and 'FDUSD' not in token['symbol'] and
             token['count'] != 0 and float(token['bidPrice']) != 0 and float(token['askPrice']) != 0])
        # 获取前一天的时间戳
        now_utc = datetime.datetime.now(timezone.utc)
        yesterday_utc = now_utc - timedelta(days=1)
        yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
        symbols_future = set(
            [token['symbol'][4:-4] if token['symbol'].startswith('1000') else token['symbol'][:-4] for token in future
             if
             token['symbol'].endswith('USDT') and 'USDC' not in token['symbol'] and 'FDUSD' not in token['symbol'] and
             token['count'] != 0 and token['closeTime'] > yesterday_timestamp_utc])
        only_spot = list(symbols_spot - symbols_future)
        only_future = list(symbols_future - symbols_spot)
        return only_spot, only_future

    else:
        print("无数据或数据格式不正确")


def binance_spot_list(endpoint="api/v3/ticker/24hr"):
    params = {}
    spot = binance_api_get(endpoint, params)

    if isinstance(spot, list) and spot:
        now_utc = datetime.datetime.now(timezone.utc)
        yesterday_utc = now_utc - timedelta(days=1)
        yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
        # 过滤出包含 "USDT" 的币种
        symbols_spot = set(
            [token['symbol'] for token in spot
             if
             token['symbol'].endswith('USDT') and 'USDC' not in token['symbol'] and 'FDUSD' not in token['symbol'] and
             token['count'] != 0 and float(token['bidPrice']) != 0 and float(token['askPrice']) != 0 and token[
                 'closeTime'] > yesterday_timestamp_utc])

        return symbols_spot

    else:
        print("无数据或数据格式不正确")


def binance_future_list():
    params = {}
    future = um_futures_client.ticker_24hr_price_change(**params)

    if isinstance(future, list) and future:
        # 获取前一天的时间戳
        now_utc = datetime.datetime.now(timezone.utc)
        yesterday_utc = now_utc - timedelta(days=1)
        yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
        symbols_future = set(
            [token['symbol'][4:-4] if token['symbol'].startswith('1000') else token['symbol'][:-4] for token in future
             if
             token['symbol'].endswith('USDT') and 'USDC' not in token['symbol'] and 'FDUSD' not in token['symbol'] and
             token['count'] != 0 and token['closeTime'] > yesterday_timestamp_utc])
        return symbols_future
    else:
        print("无数据或数据格式不正确")


def fetch_gain_lose_spot(symbol, interval, limit):
    try:
        if symbol in ['SATSUSDT']:
            symbol = '1000' + symbol
        k_line = get_k_lines(symbol, interval, limit)

        start_price = float(k_line[0][1])
        # 过滤新币
        lowest_price = float(k_line[0][3])
        if start_price == lowest_price:
            return None
        highest_price = float(max(item[2] for item in k_line))

        price_chg = int(round(highest_price / start_price * 100, 0))
        if price_chg < 150:
            return None
        return [symbol[:-4], price_chg]
    except Exception as e:
        if 'invalid symbol' in str(e).lower():
            try:
                symbol = '1000' + symbol
                k_line = get_k_lines(symbol, interval, limit)

                start_price = float(k_line[0][1])
                # 过滤新币
                lowest_price = float(k_line[0][3])
                if start_price == lowest_price:
                    return None
                highest_price = float(max(item[2] for item in k_line))

                price_chg = int(round(highest_price / start_price * 100, 0))
                if price_chg < 150:
                    return None
                return [symbol[:-4], price_chg]
            except Exception as e2:
                print(f"Failed to fetch data for both {symbol} and 1000{symbol}: {e2}")
                return None
        else:
            # 其他异常错误
            print(f"Failed to fetch data: {e}")
            return None


def fetch_gain_lose_future(symbol, interval, limit):
    try:
        para = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        k_line = um_futures_client.klines(**para)

        start_price = float(k_line[0][1])
        # 过滤新币
        lowest_price = float(k_line[0][3])
        if start_price == lowest_price:
            return None
        highest_price = float(max(item[2] for item in k_line))

        price_chg = int(round(highest_price / start_price * 100, 0))
        if price_chg < 150:
            return None
        return [symbol[:-4], price_chg]
    except Exception as e:
        if 'invalid symbol' in str(e).lower():
            try:
                symbol = '1000' + symbol

                para = {
                    'symbol': symbol,
                    'interval': interval,
                    'limit': limit
                }
                k_line = um_futures_client.klines(**para)

                start_price = float(k_line[0][1])
                # 过滤新币
                lowest_price = float(k_line[0][3])
                if start_price == lowest_price:
                    return None
                highest_price = float(max(item[2] for item in k_line))

                price_chg = int(round(highest_price / start_price * 100, 0))
                if price_chg < 150:
                    return None
                return [symbol[:-4], price_chg]

            except Exception as e2:
                print(f"Failed to fetch data for both {symbol} and 1000{symbol}: {e2}")
                return None
        else:
            # 其他异常错误
            print(f"Failed to fetch data: {e}")
            return None


def get_gain_lose_rank(interval, limit, endpoint="api/v3/ticker/24hr"):
    try:
        params = {}
        spot = binance_api_get(endpoint, params)
        future = um_futures_client.ticker_24hr_price_change(**params)
        price_chg_res = []
        interval_str = "周" if interval[-1:] == 'w' else "日" if interval[-1:] == 'd' else "月" if interval[
                                                                                                -1:] == 'M' else "小时"
        res_str = f"🏆*以下是近{limit}{interval_str}币种涨幅情况：*\n"

        if isinstance(spot, list) and spot and isinstance(future, list) and future:
            # 过滤出包含 "USDT" 的币种
            symbols_spot = set(
                [token['symbol'][4:] if token['symbol'].startswith('1000') else token['symbol'] for token in spot
                 if
                 token['symbol'].endswith('USDT') and 'USDC' not in token['symbol'] and 'FDUSD' not in token[
                     'symbol'] and 'BTCDOM' not in token['symbol'] and token['count'] != 0 and float(
                     token['bidPrice']) != 0 and float(token['askPrice']) != 0])
            # 获取前一天的时间戳
            now_utc = datetime.datetime.now(timezone.utc)
            yesterday_utc = now_utc - timedelta(days=1)
            yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
            symbols_future = set(
                [token['symbol'][4:] if token['symbol'].startswith('1000') else token['symbol'] for token in future
                 if
                 token['symbol'].endswith('USDT') and 'USDC' not in token['symbol'] and 'FDUSD' not in token[
                     'symbol'] and 'BTCDOM' not in token['symbol'] and token['count'] != 0 and token[
                     'closeTime'] > yesterday_timestamp_utc])
            only_future = list(symbols_future - symbols_spot)

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_gain_lose_spot, symbol, interval, limit) for symbol in symbols_spot]

                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        price_chg_res.append(result)

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_gain_lose_future, symbol, interval, limit) for symbol in only_future]

                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        price_chg_res.append(result)

            filtered_sorted_list = sorted(price_chg_res, key=lambda x: x[1], reverse=True)

            filtered_sorted_list_500 = [item for item in filtered_sorted_list if item[1] >= 500]
            if len(filtered_sorted_list_500) > 0:
                res_str += "\n🥇`5倍以上：`\n"
                for fsl in filtered_sorted_list_500:
                    sym = fsl[0]
                    pchg = fsl[1]
                    res_str += f"🪙*{sym}*: {pchg}%\n"
            else:
                res_str += "\n🥇`5倍以上：`*无*\n"

            filtered_sorted_list_200 = [item for item in filtered_sorted_list if 300 <= item[1] < 500]
            if len(filtered_sorted_list_200) > 0:
                res_str += "\n🥈`3倍以上：`\n"
                for fsl in filtered_sorted_list_200:
                    sym = fsl[0]
                    pchg = fsl[1]
                    res_str += f"🪙*{sym}*: {pchg}%\n"
            else:
                res_str += "\n🥈`3倍以上：`*无*\n"

            filtered_sorted_list_100 = [item for item in filtered_sorted_list if 200 <= item[1] < 300]
            if len(filtered_sorted_list_100) > 0:
                res_str += "\n🥉`2倍以上：`\n"
                for fsl in filtered_sorted_list_100:
                    sym = fsl[0]
                    pchg = fsl[1]
                    res_str += f"🪙*{sym}*: {pchg}%\n"
            else:
                res_str += "\n🥉`2倍以上：`*无*\n"

            filtered_sorted_list_50 = [item for item in filtered_sorted_list if 160 < item[1] < 200]
            if len(filtered_sorted_list_50) > 0:
                res_str += "\n👏`1.6倍以上：`\n"
                for fsl in filtered_sorted_list_50:
                    sym = fsl[0]
                    pchg = fsl[1]
                    res_str += f"🪙*{sym}*: {pchg}%\n"
            else:
                res_str += "\n👏`1.6倍以上：`*无*\n"
        return res_str
    except Exception as e:
        print(e)
        return None


def get_symbol_net_v(symbol):
    interval_list = ["5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "16h", "20h", "1d", "2d", "3d", "4d",
                     "5d"]
    res = []
    f = True
    s = True
    for interval in interval_list:
        limit = parse_interval_to_5minutes(interval)
        net_future = None
        net_spot = None
        if f:
            try:
                para = {
                    'symbol': symbol if symbol not in symbol1000 else '1000' + symbol,
                    'interval': '5m',
                    'limit': limit
                }
                k_line_future = um_futures_client.klines(**para)
                net = 0
                for k in k_line_future:
                    price = float(k[4])
                    v = float(k[5])
                    taker = float(k[9])
                    maker = v - taker
                    net_volume = (taker - maker) * price
                    net += net_volume
                net_future = net
            except Exception as e:
                f = False
        if s:
            para = {
                'symbol': symbol,
                'interval': '5m',
                'limit': limit
            }
            k_line_spot = get_k_lines(**para)
            if not k_line_spot:
                s = False
            else:
                net = 0
                for k in k_line_spot:
                    price = float(k[4])
                    v = float(k[5])
                    taker = float(k[9])
                    maker = v - taker
                    net_volume = (taker - maker) * price
                    net += net_volume
                net_spot = net
        if not net_future and not net_spot:
            return None
        else:
            if net_future and net_spot:
                res.append([interval, round(net_future, 2), round(net_spot, 2)])
            elif net_future and not net_spot:
                res.append([interval, round(net_future, 2), None])
            else:
                res.append([interval, None, round(net_spot, 2)])
    return res


def statistic_coin_time(symbol):
    try:
        k = get_k_lines(symbol, '1h', 1000)
        if not k:
            k = get_k_lines_future(symbol, '1h', 1000)
            if not k:
                return None

        # 分别存储拉盘和砸盘结果
        pump_res = []  # 拉盘结果
        dump_res = []  # 砸盘结果

        for i in k:
            timestamp_ms = i[0]
            # 将毫秒转换为秒，并创建 UTC 时间
            utc_time = datetime.datetime.utcfromtimestamp(timestamp_ms / 1000)
            # 转换为 UTC+8 时间（加 8 小时）
            utc8_time = utc_time + timedelta(hours=8)
            # 提取小时数（24小时制）
            hour = utc8_time.hour

            if i[1] < i[4]:  # 开盘价 < 收盘价，拉盘
                pump_res.append([hour, 1])
                dump_res.append([hour, 0])
            else:  # 开盘价 ≥ 收盘价，砸盘
                pump_res.append([hour, 0])
                dump_res.append([hour, 1])

        # 处理拉盘数据
        pump_first_nums = [sub[0] for sub in pump_res if sub[1] == 1]
        pump_count_dict = {}
        for num in pump_first_nums:
            pump_count_dict[num] = pump_count_dict.get(num, 0) + 1
        pump_result = [[num, count] for num, count in pump_count_dict.items()]
        pump_result.sort(key=lambda x: x[1], reverse=True)

        pump_t = {}
        for first, second in pump_result:
            if second not in pump_t:
                pump_t[second] = []
            pump_t[second].append(first)

        # 处理砸盘数据
        dump_first_nums = [sub[0] for sub in dump_res if sub[1] == 1]
        dump_count_dict = {}
        for num in dump_first_nums:
            dump_count_dict[num] = dump_count_dict.get(num, 0) + 1
        dump_result = [[num, count] for num, count in dump_count_dict.items()]
        dump_result.sort(key=lambda x: x[1], reverse=True)

        dump_t = {}
        for first, second in dump_result:
            if second not in dump_t:
                dump_t[second] = []
            dump_t[second].append(first)

        # 生成输出字符串
        str = f"📊*{symbol[:-4]}*近期价格波动时间点统计：\n\n"

        # 拉盘统计
        str += "📈 拉盘时间点统计：\n"
        for i, (k, v) in enumerate(pump_t.items()):
            if i > 2:
                break
            st = ""
            for tz in v:
                st += f"`{tz}`点|"
            if i == 0:
                pre = "1️⃣最容易拉盘的时间点是："
            elif i == 1:
                pre = "2️⃣第二容易拉盘的时间点是："
            else:
                pre = "3️⃣第三容易拉盘的时间点是："
            str += f"{pre}{st}一共拉盘过{k}次\n"

        # 砸盘统计
        str += "\n📉 砸盘时间点统计：\n"
        for i, (k, v) in enumerate(dump_t.items()):
            if i > 2:
                break
            st = ""
            for tz in v:
                st += f"`{tz}`点|"
            if i == 0:
                pre = "1️⃣最容易砸盘的时间点是："
            elif i == 1:
                pre = "2️⃣第二容易砸盘的时间点是："
            else:
                pre = "3️⃣第三容易砸盘的时间点是："
            str += f"{pre}{st}一共砸盘过{k}次\n"

        return str

    except Exception as e:
        print(f"无法统计币和时间：{e}")
        return None


def create_token_time_plot(symbol):
    try:
        k = get_k_lines(symbol, '1h', 1000)
        if not k:
            k = get_k_lines_future(symbol, '1h', 1000)
            if not k:
                return None

        data = []

        for i in k:
            timestamp_ms = i[0]
            # 将毫秒转换为秒，并创建 UTC 时间
            utc_time = datetime.datetime.utcfromtimestamp(timestamp_ms / 1000)
            # 转换为 UTC+8 时间（加 8 小时）
            utc8_time = utc_time + timedelta(hours=8)
            # 提取小时数（24小时制）
            hour = utc8_time.hour

            data.append((hour, (float(i[4]) - float(i[1])) * 100 / float(i[1]))) if float(i[1]) != 0 else 0
        # 初始化24小时的涨幅数组
        hours = list(range(24))  # 0到23小时
        gains_sum = [0] * 24  # 每个小时的涨幅总和
        counts = [0] * 24  # 每个小时的数据点计数

        # 聚合数据：按小时累加涨幅并计数
        for hour, gain in data:
            if 0 <= hour <= 23:  # 确保小时数有效
                gains_sum[hour] += gain
                counts[hour] += 1

        # 计算每个小时的平均涨幅（如果没有数据，设为0）
        average_gains = [gains_sum[i] / counts[i] if counts[i] > 0 else 0 for i in range(24)]

        # 设置柱子颜色：涨幅>0用绿色，<0用红色
        colors = ['green' if gain > 0 else 'red' if gain < 0 else 'skyblue' for gain in average_gains]

        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']  # 优先使用 SimHei，支持中文
        plt.rcParams['axes.unicode_minus'] = False

        # 创建柱状图
        plt.figure(figsize=(16, 8))  # 设置图形大小
        bars = plt.bar(hours, average_gains, color=colors, edgecolor='black', width=0.4)

        # 设置图表标题和标签
        plt.title('一天中每小时平均涨幅', fontsize=14)
        plt.xlabel('小时点', fontsize=12)
        plt.ylabel('平均涨幅 (%)', fontsize=12)

        # 设置x轴为整点
        plt.xticks(hours, [f'{h}:00' for h in hours], rotation=45)

        # 添加网格线
        plt.grid(True, axis='y', linestyle='--', alpha=0.7)

        # 设置y轴以0为中心，自动调整范围
        plt.axhline(y=0, color='black', linewidth=1)  # 添加y=0的水平线
        plt.margins(y=0.1)  # 增加y轴上下边距，避免柱子贴边

        # 动态调整y轴范围，确保正负对称
        max_abs_gain = max(abs(min(average_gains)), abs(max(average_gains)))
        plt.ylim(-max_abs_gain * 1.2, max_abs_gain * 1.2)  # 设置y轴范围，1.2倍留出空间

        # 调整布局以防止标签被裁剪
        plt.tight_layout()

        # 保存到内存
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        print(f"无法绘画：{e}")
        return None


def statistic_token_time(symbol):
    try:
        k = get_k_lines(symbol, '1h', 1000)
        if not k:
            k = get_k_lines_future(symbol, '1h', 1000)
            if not k:
                return None

        pump_res = []  # 拉盘结果
        dump_res = []  # 砸盘结果
        gains = []  # 涨幅结果

        for i in k:
            timestamp_ms = i[0]
            utc_time = datetime.datetime.utcfromtimestamp(timestamp_ms / 1000)
            utc8_time = utc_time + timedelta(hours=8)
            hour = utc8_time.hour
            open_price = float(i[1])
            close_price = float(i[4])

            # 计算涨幅（百分比）
            gain = ((close_price - open_price) / open_price) * 100 if open_price != 0 else 0
            gains.append([hour, gain])

            # 拉盘/砸盘逻辑
            if open_price < close_price:  # 拉盘
                pump_res.append([hour, 1])
                dump_res.append([hour, 0])
            else:  # 砸盘（包含相等情况）
                pump_res.append([hour, 0])
                dump_res.append([hour, 1])

        # 处理拉盘数据
        pump_first_nums = [sub[0] for sub in pump_res if sub[1] == 1]
        pump_count_dict = {}
        for num in pump_first_nums:
            pump_count_dict[num] = pump_count_dict.get(num, 0) + 1
        pump_result = [[num, count] for num, count in pump_count_dict.items()]

        # 处理砸盘数据
        dump_first_nums = [sub[0] for sub in dump_res if sub[1] == 1]
        dump_count_dict = {}
        for num in dump_first_nums:
            dump_count_dict[num] = dump_count_dict.get(num, 0) + 1
        dump_result = [[num, count] for num, count in dump_count_dict.items()]

        return {symbol: {'pump': pump_result, 'dump': dump_result, 'gains': gains}}

    except Exception as e:
        print(f"无法统计币和时间：{e}")
        return None


# 计算每个时间的平均 count 并排序
def calculate_time_averages(data, type='pump'):
    time_counts = {}
    for item in data:
        for symbol, results in item.items():
            time_list = results[type]
            for time, count in time_list:
                if time not in time_counts:
                    time_counts[time] = {'sum': 0, 'count': 0}
                time_counts[time]['sum'] += count
                time_counts[time]['count'] += 1

    time_averages = {}
    for time, stats in time_counts.items():
        time_averages[time] = stats['sum'] / stats['count']

    sorted_times = sorted(time_averages.items(), key=lambda x: x[1], reverse=True)
    return sorted_times[:5]


# 对于特定时间，找出 count 最大的 symbol
def get_top_symbols_for_time(data, target_time, type='pump'):
    symbol_counts = []
    for item in data:
        for symbol, results in item.items():
            time_list = results[type]
            for time, count in time_list:
                if time == target_time:
                    symbol_counts.append((symbol, count))

    sorted_symbols = sorted(symbol_counts, key=lambda x: x[1], reverse=True)
    return sorted_symbols[:10]


# 新增：计算每个小时的平均涨幅
def calculate_hourly_average_gains(data):
    hourly_gains = {hour: {'sum': 0, 'count': 0} for hour in range(24)}
    for item in data:
        for symbol, results in item.items():
            for hour, gain in results.get('gains', []):
                if 0 <= hour <= 23:
                    hourly_gains[hour]['sum'] += gain
                    hourly_gains[hour]['count'] += 1

    average_gains = [hourly_gains[hour]['sum'] / hourly_gains[hour]['count']
                     if hourly_gains[hour]['count'] > 0 else 0
                     for hour in range(24)]
    return average_gains


# 新增：生成24小时平均涨幅柱状图
def create_all_tokens_time_plot():
    hours = list(range(24))
    average_gains = calculate_hourly_average_gains(stat)  # 使用全局 stat 数据

    colors = ['green' if gain > 0 else 'red' if gain < 0 else 'skyblue' for gain in average_gains]

    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']  # 优先使用 SimHei，支持中文
    plt.rcParams['axes.unicode_minus'] = False

    plt.figure(figsize=(16, 8))
    plt.bar(hours, average_gains, color=colors, edgecolor='black', width=0.4)
    plt.title('所有币种24小时平均涨跌幅', fontsize=14)  # 中文标题
    plt.xlabel('时间 (小时)', fontsize=12)
    plt.ylabel('平均涨跌幅 (%)', fontsize=12)
    plt.xticks(hours, [f'{h}:00' for h in hours], rotation=45)
    plt.grid(True, axis='y', linestyle='--', alpha=0.7)
    plt.axhline(y=0, color='black', linewidth=1)
    plt.margins(y=0.1)
    max_abs_gain = max(abs(min(average_gains)), abs(max(average_gains)))
    plt.ylim(-max_abs_gain * 1.2, max_abs_gain * 1.2)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf


# 新增：获取当前时间点的涨幅/跌幅排行榜
def get_top_gains_for_time(data, target_time):
    symbol_gains = []
    for item in data:
        for symbol, results in item.items():
            for hour, gain in results.get('gains', []):
                if hour == target_time:
                    symbol_gains.append((symbol, gain))

    # 分离涨幅和跌幅
    gains = [(s, g) for s, g in symbol_gains if g > 0]
    losses = [(s, g) for s, g in symbol_gains if g < 0]

    # 按涨幅/跌幅排序
    top_gains = sorted(gains, key=lambda x: x[1], reverse=True)[:10]
    top_losses = sorted(losses, key=lambda x: x[1])[:10]  # 跌幅最负（最小）

    return top_gains, top_losses


# 修改 statistic_time 函数，添加平均涨幅和排行榜
def statistic_time(endpoint='api/v3/ticker/24hr'):
    global stat
    try:
        params = {}
        result = binance_api_get(endpoint, params)
        result_future = um_futures_client.ticker_24hr_price_change(**params)
        res = result
        res1 = result_future
        now_utc = datetime.datetime.now(timezone.utc)
        yesterday_utc = now_utc - timedelta(days=1)
        yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000

        if isinstance(res, list) and res and isinstance(res1, list) and res1:
            result_dict = {item['symbol'][4:] if item['symbol'].startswith("1000") else item['symbol']: item for item in
                           res}
            for item in res1:
                sym = item['symbol'][4:] if item['symbol'].startswith("1000") else item['symbol']
                if sym not in result_dict:
                    result_dict[sym] = item
            result_list = list(result_dict.values())

            fil_str_list = ['USDC', 'FDUSD', 'TUSDUSDT', 'USDP', 'EUR']
            tokens = [
                token['symbol'] for token in result_list
                if token['symbol'].endswith("USDT")
                   and all(f not in token['symbol'] for f in fil_str_list)
                   and token['count'] != 0
                   and token['closeTime'] > yesterday_timestamp_utc
            ]

            stat = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(statistic_token_time, symbol) for symbol in tokens]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        stat.append(result)

            res_str = "📊全局统计价格波动时间点：\n\n"

            # 拉盘统计
            res_str += "📈 拉盘最多的时间点：\n"
            pump_time_averages = calculate_time_averages(stat, 'pump')
            for time, avg in pump_time_averages:
                res_str += f"`{time}`点，平均拉盘次数: {avg:.1f}\n"

            # 砸盘统计
            res_str += "\n📉 砸盘最多的时间点：\n"
            dump_time_averages = calculate_time_averages(stat, 'dump')
            for time, avg in dump_time_averages:
                res_str += f"`{time}`点，平均砸盘次数: {avg:.1f}\n"

            # 当前时间统计
            utc_time = datetime.datetime.utcnow()
            utc8_time = utc_time + timedelta(hours=8)
            target_time = utc8_time.hour

            res_str += f"\n🕒此时*{target_time}*点：\n"
            # 当前时间的拉盘统计
            res_str += "📈 拉盘次数最多的symbol：\n"
            pump_top_symbols = get_top_symbols_for_time(stat, target_time, 'pump')
            for symbol, count in pump_top_symbols:
                res_str += f"`{symbol[:-4]}`：{count}\n"

            # 当前时间的砸盘统计
            res_str += "\n📉 砸盘次数最多的symbol：\n"
            dump_top_symbols = get_top_symbols_for_time(stat, target_time, 'dump')
            for symbol, count in dump_top_symbols:
                res_str += f"`{symbol[:-4]}`：{count}\n"

            # 新增：当前时间的涨幅/跌幅排行榜
            res_str += "\n📊 当前时间点涨幅/跌幅排行：\n"
            top_gains, top_losses = get_top_gains_for_time(stat, target_time)
            res_str += "📈 涨幅最大的symbol：\n"
            if top_gains:
                for symbol, gain in top_gains:
                    res_str += f"`{symbol[:-4]}`：{gain:.2f}%\n"
            else:
                res_str += "无上涨数据\n"
            res_str += "\n📉 跌幅最大的symbol：\n"
            if top_losses:
                for symbol, loss in top_losses:
                    res_str += f"`{symbol[:-4]}`：{loss:.2f}%\n"
            else:
                res_str += "无下跌数据\n"

            return res_str

    except Exception as e:
        print(f"无法统计币和时间：{e}")
        return None


def map_cmc_symbol(symbol):
    symbol_dict = {
        "luna2": "luna",
        "ronin": "ron",
        "000mog": "mog",
        "sonic": "s",
        "1mbabydoge": 'babydoge',
        "raysol": 'ray'
    }
    return symbol_dict.get(symbol, symbol)


def get_speicial_supply(symbol):
    supply = {
        "velodrome": 2014733589.72,
        "neiroeth": 1000000000,
        "quick": 749764355.6046581,
        "avaai": 999994070
    }
    return supply.get(symbol, None)


def get_upbit_volume_increase_15(symbol):
    try:
        data15 = get_k_lines(symbol, '15m', 2)
        # 再看15min内是否有交易量激增
        v_now = float(data15[1][7])
        v_past = float(data15[0][7])
        v_ratio = round(float(v_now / v_past), 2)
        if v_ratio >= 3:
            v15_list = [1, v_ratio]
        else:
            v15_list = [0, v_ratio]
        return v15_list
    except Exception as e:
        data15 = get_k_lines_future(symbol, '15m', 2)
        # 再看15min内是否有交易量激增
        v_now = float(data15[1][7])
        v_past = float(data15[0][7])
        v_ratio = round(float(v_now / v_past), 2)
        if v_ratio >= 3:
            v15_list = [1, v_ratio]
        else:
            v15_list = [0, v_ratio]
        return v15_list


def get_oi_increase(symbol, limit=100):
    if symbol in symbol1000:
        symbol = "1000" + symbol
    para = {
        'symbol': symbol,
        'period': '15m',
        'limit': limit
    }
    openInterest = um_futures_client.open_interest_hist(**para)
    if not openInterest:
        return None, None
    else:
        increase_num = 0
        decrease_num = 0
        for i in range(len(openInterest) - 1, -1, -1):
            if float(openInterest[i]['sumOpenInterest']) > float(openInterest[i - 1]['sumOpenInterest']):
                increase_num += 1
            else:
                break
        if increase_num == 0:
            for i in range(len(openInterest) - 1, -1, -1):
                if float(openInterest[i]['sumOpenInterest']) < float(openInterest[i - 1]['sumOpenInterest']):
                    decrease_num += 1
                else:
                    break
        return increase_num, decrease_num
