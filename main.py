import requests
import random
import datetime
from binance.um_futures import UMFutures

um_futures_client = UMFutures()


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
        response = requests.get(url, params=params)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            return response.json()  # Return JSON response
        else:
            print(f"Failed to fetch data from {url}. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"Error making request to {url}: {e}")

    return None  # Return None if the request fails


def get_gain_loss(rank=30, endpoint="api/v3/ticker/24hr"):
    params = {}
    result = binance_api_get(endpoint, params)
    res = result

    # 假设 res 是一个列表，每个元素是一个字典，包含 'symbol' 和 'priceChangePercent' 字段

    # 检查 res 是否是列表，确保不是空列表
    if isinstance(res, list) and res:
        # 按涨幅排序
        sorted_res_rise = sorted(res, key=lambda x: float(x['priceChangePercent']), reverse=True)

        # 过滤出包含 "USDT" 的币种
        usdt_symbols_rise = [token['symbol'] for token in sorted_res_rise if 'USDT' in token['symbol']]

        # 打印涨幅榜前十
        print("涨幅榜：")
        for i, symbol in enumerate(usdt_symbols_rise[:rank]):
            print(
                f"{i + 1}. {symbol[:-4]} - 涨幅：{next(token['priceChangePercent'] for token in sorted_res_rise if token['symbol'] == symbol)}%")

        # 按跌幅排序
        sorted_res_fall = sorted(res, key=lambda x: float(x['priceChangePercent']))

        # 过滤出包含 "USDT" 的币种
        usdt_symbols_fall = [token['symbol'] for token in sorted_res_fall if 'USDT' in token['symbol']]

        # 打印跌幅榜前十
        print("\n跌幅榜前十：")
        for i, symbol in enumerate(usdt_symbols_fall[:rank]):
            print(
                f"{i + 1}. {symbol[:-4]} - 跌幅：{next(token['priceChangePercent'] for token in sorted_res_fall if token['symbol'] == symbol)}%")
    else:
        print("无数据或数据格式不正确")


def recommend(cir_df, rank=25, endpoint="api/v3/ticker/24hr"):
    recommend_list = []
    params = {}
    result = binance_api_get(endpoint, params)
    res = result

    # 假设 res 是一个列表，每个元素是一个字典，包含 'symbol' 和 'priceChangePercent' 字段

    # 检查 res 是否是列表，确保不是空列表
    if isinstance(res, list) and res:
        # 按涨幅排序
        sorted_res_rise = sorted(res, key=lambda x: float(x['priceChangePercent']), reverse=True)

        # 过滤出包含 "USDT" 的币种
        usdt_symbols_rise = [[token['symbol'], token['quoteVolume']] for token in sorted_res_rise if
                             'USDT' in token['symbol']]

        for symbol_list in usdt_symbols_rise[:rank]:
            symbol = symbol_list[0]
            circle_supply = get_circulating_supply(symbol[:-4].lower(), cir_df)
            if not circle_supply:
                continue
            flag = []
            p_len4, v_len4, vc_ratio, taker_ratio4 = get_price_volume_increase(symbol, '4h', 5, circle_supply)
            if p_len4 >= 3 and v_len4 >= 2:
                flag.append([1, p_len4, v_len4])
            if vc_ratio > 0.05:
                flag.append([3, vc_ratio])
            if taker_ratio4 > 0.5:
                flag.append([9, taker_ratio4])

            p_len1, v_len1, vc_ratio, taker_ratio1 = get_price_volume_increase(symbol, '1h', 7, circle_supply)
            if p_len1 >= 5 and v_len1 >= 4:
                flag.append([2, p_len1, v_len1])
            if taker_ratio1 > 0.5:
                flag.append([10, taker_ratio1])

            v15_list = get_volume_increase_15(symbol)
            if v15_list[0] == 1:
                flag.append([4, v15_list[1]])

            buy_spot = search_more_big_buy_spot(symbol)
            buy_future = search_more_big_buy_future(symbol)
            for i in range(3):
                if buy_spot[i] == 1 or buy_future == 1:
                    flag.append([5, buy_spot, buy_future])
                    break

            longshortRatio_rate1 = get_future_takerlongshortRatio(symbol, '1h')
            longshortRatio_rate4 = get_future_takerlongshortRatio(symbol, '4h')
            if longshortRatio_rate1:
                if longshortRatio_rate1 > 0.1:
                    flag.append([7, longshortRatio_rate1])
            if longshortRatio_rate4:
                if longshortRatio_rate4 > 0.1:
                    flag.append([8, longshortRatio_rate4])
            # agg_spot = get_aggTrades_spot(symbol)
            # agg_future = get_aggTrades_future(symbol)
            # if len(agg_spot) > 0 or len(agg_future) > 0:
            #     flag.append([6, agg_spot, agg_future])
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
    data = get_k_lines(symbol, interval, limit)

    volume_list = []
    endprice_list = []

    # 先看1h/4h红绿绿以及绿绿绿趋势,以及交易量趋势
    for l in data:
        endprice = float(l[4])
        vol = float(l[7])
        endprice_list.append(endprice)
        volume_list.append(vol)
    p_len = max_increasing_length(endprice_list)
    v_len = max_increasing_length(volume_list, is_volume=1)

    # 再看交易量占比
    flag = -2 if volume_list[-2] > volume_list[-1] else -1
    volume = volume_list[flag]
    price = endprice_list[flag]
    cmc = circle_supply * price
    vc_ratio = round(float(volume / cmc), 2)

    # 看主动成交额占比
    taker_vol0 = float(data[0][10])
    vol0 = float(data[0][7])
    taker_ratio = round(taker_vol0 / vol0, 2)

    return p_len, v_len, vc_ratio, taker_ratio


def get_volume_increase_15(symbol):
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


def get_k_lines(symbol, interval, limit, endpoint="api/v3/klines"):
    para = {
        'symbol': symbol,
        'interval': interval,
        'limit': limit
    }
    data = binance_api_get(endpoint, para)
    return data


def get_latest_price(symbol, endpoint='api/v3/ticker/price'):
    para = {
        'symbol': symbol
    }
    data = binance_api_get(endpoint, para)
    return float(data['price'])


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
    para = {
        'symbol': symbol,
        'period': period
    }
    data = binance_api_get(endpoint, para)
    return data


def search_more_big_buy_spot(symbol, order_value=None, limit=5000, endpoint='api/v3/depth',
                             bpr=0.1, spr=0.1):
    if order_value is None:
        order_value = [100000, 500000, 1000000]
    try:
        para = {
            'symbol': symbol,
            'limit': limit
        }
        data = binance_api_get(endpoint, para)
        sp = float(get_latest_price(symbol))

        buy = [0, 0, 0]
        for l in data['bids']:
            p = float(l[0])
            v = int(p * float(l[1]))
            for i, ov in enumerate(order_value):
                if sp * (1 - bpr) <= p and v >= ov:
                    buy[i] += v

        sell = [0, 0, 0]
        for l in data['asks']:
            p = float(l[0])
            v = int(p * float(l[1]))
            for i, ov in enumerate(order_value):
                if p <= sp * (1 + spr) and v >= ov:
                    sell[i] += v

        res = []
        for i in range(len(order_value)):
            if buy[i] > sell[i]:
                res.append(1)
            else:
                res.append(0)
        return res
    except Exception as e:
        return [0, 0, 0]


def search_more_big_buy_future(symbol, order_value=None, limit=1000, bpr=0.1, spr=0.1):
    if order_value is None:
        order_value = [100000, 500000, 1000000]
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

        buy = [0, 0, 0]
        for l in data['bids']:
            p = float(l[0])
            v = int(p * float(l[1]))
            for i, ov in enumerate(order_value):
                if fp * (1 - bpr) <= p and v >= ov:
                    buy[i] += v

        sell = [0, 0, 0]
        for l in data['asks']:
            p = float(l[0])
            v = int(p * float(l[1]))
            for i, ov in enumerate(order_value):
                if p <= fp * (1 + spr) and v >= ov:
                    sell[i] += v

        res = []
        for i in range(len(order_value)):
            if buy[i] > sell[i]:
                res.append(1)
            else:
                res.append(0)
        return res
    except Exception as e:
        return [0, 0, 0]


def get_aggTrades_spot(symbol, endpoint='api/v3/aggTrades', target=100000):
    para = {
        'symbol': symbol
    }
    data = binance_api_get(endpoint, para)

    res = []
    for d in data:
        if d['m']:
            v = float(d['p']) * float(d['q'])
            if v >= target:
                res.append(v)
    return res


def get_aggTrades_future(symbol, target=100000):
    try:
        para = {
            'symbol': symbol
        }
        data = um_futures_client.agg_trades(**para)

        res = []
        for d in data:
            if d['m']:
                v = float(d['p']) * float(d['q'])
                if v >= target:
                    res.append(v)
        return res
    except Exception as e:
        return []


def scan_big_order_spot(symbol, limit=1000, endpoint='api/v3/aggTrades', target=100000):
    buy = []
    sell = []

    para = {
        'symbol': symbol,
        'limit': limit
    }
    data = binance_api_get(endpoint, para)

    sp = get_latest_price(symbol)
    for d in data:
        p = float(d['p'])
        v = p * float(d['q'])
        if v >= target:
            if p >= sp:
                buy.append([v, d['T']])
            else:
                sell.append([v, d['T']])
    return buy, sell


def scan_big_order_future(symbol, limit=1000, target=100000):
    try:
        buy = []
        sell = []

        para = {
            'symbol': symbol,
            'limit': limit
        }
        data = um_futures_client.agg_trades(**para)

        fp = um_futures_client.ticker_price(**para)
        for d in data:
            p = float(d['p'])
            v = p * float(d['q'])
            if v >= target:
                if p >= fp:
                    buy.append([v, d['T']])
                else:
                    sell.append([v, d['T']])
        return buy, sell
    except Exception as e:
        return [], []


def scan_big_order(record, endpoint='api/v3/ticker/24hr', rank=15):
    recommend_list = []
    params = {}
    result = binance_api_get(endpoint, params)
    res = result

    # 假设 res 是一个列表，每个元素是一个字典，包含 'symbol' 和 'priceChangePercent' 字段

    # 检查 res 是否是列表，确保不是空列表
    if isinstance(res, list) and res:
        # 按涨幅排序
        sorted_res_rise = sorted(res, key=lambda x: float(x['priceChangePercent']), reverse=True)

        # 过滤出包含 "USDT" 的币种
        usdt_symbols_rise = [[token['symbol'], token['quoteVolume']] for token in sorted_res_rise if
                             'USDT' in token['symbol']]

        for symbol_list in usdt_symbols_rise[:rank]:
            symbol = symbol_list[0]
            buy_spot, sell_spot = scan_big_order_spot(symbol)
            buy_future, sell_future = scan_big_order_future(symbol)
            spot = []
            future = []
            if len(buy_spot) > 0:
                for v in buy_spot:
                    if v[1] not in record:
                        spot.append([1, v[0]])
                        record.add(v[1])
            if len(sell_spot) > 0:
                for v in sell_spot:
                    if v[1] not in record:
                        spot.append([0, v[0]])
                        record.add(v[1])
            if len(buy_future) > 0:
                for v in buy_future:
                    if v[1] not in record:
                        future.append([1, v[0]])
                        record.add(v[1])
            if len(sell_future) > 0:
                for v in sell_future:
                    if v[1] not in record:
                        future.append([0, v[0]])
                        record.add(v[1])
            if len(spot) > 0 or len(future) > 0:
                price = get_latest_price(symbol)
                recommend_list.append({symbol[:-4]: [price, [spot, future]]})
    return recommend_list


def get_future_takerlongshortRatio(symbol, interval):
    try:
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


def get_taker_vol_delta(symbol, interval):
    try:
        para = {
            'symbol': symbol,
            'period': interval,
            'limit': 1
        }

        data = um_futures_client.taker_long_short_ratio(**para)

        taker_vol_delta = float(data[0]['buyVol']) - float(data[0]['sellVol'])

        return taker_vol_delta
    except Exception as e:
        return None

# syb = 'OSMOUSDT'
# p = get_future_takerlongshortRatio(syb, '1h')
# print(p)
