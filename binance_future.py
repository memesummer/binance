# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2024/5/29 14:43
#    @Description   : 
#
# ==============================================================
import concurrent.futures
import datetime
from datetime import timedelta, timezone

from binance.um_futures import UMFutures

from main import binance_api_get, get_latest_price, symbol1000

um_futures_client = UMFutures()


def get_future_pending_order_rank(symbol, order_value, limit=1000, bpr=0.1, spr=0.1):
    try:
        para = {
            'symbol': symbol,
            'limit': limit
        }
        data = um_futures_client.depth(**para)
        fp = get_future_price(symbol)

        res = []
        for l in data['bids']:
            v = int(float(l[0]) * float(l[1]))
            if v >= order_value:
                res.append([float(l[0]), v])

        sorted_list1 = sorted(res, key=lambda x: x[1], reverse=True)
        filtered_list1 = [sublist for sublist in sorted_list1 if sublist[0] >= fp * (1 - bpr)]

        res = []
        for l in data['asks']:
            v = int(float(l[0]) * float(l[1]))
            if v >= order_value:
                res.append([float(l[0]), v])

        sorted_list2 = sorted(res, key=lambda x: x[1], reverse=True)
        filtered_list2 = [sublist for sublist in sorted_list2 if sublist[0] <= fp * (1 + spr)]

        return filtered_list1, filtered_list2
    except Exception as e:
        return None, None


def get_spot_pending_order_rank(symbol, order_value, limit=5000, endpoint='api/v3/depth', bpr=0.1, spr=0.1):
    try:
        para = {
            'symbol': symbol,
            'limit': limit
        }
        data = binance_api_get(endpoint, para)
        sp = float(get_latest_price(symbol))

        res = []
        for l in data['bids']:
            v = int(float(l[0]) * float(l[1]))
            if v >= order_value:
                res.append([float(l[0]), v])

        sorted_list1 = sorted(res, key=lambda x: x[1], reverse=True)
        filtered_list1 = [sublist for sublist in sorted_list1 if sublist[0] >= sp * (1 - bpr)]

        res = []
        for l in data['asks']:
            v = int(float(l[0]) * float(l[1]))
            if v >= order_value:
                res.append([float(l[0]), v])

        sorted_list2 = sorted(res, key=lambda x: x[1], reverse=True)
        filtered_list2 = [sublist for sublist in sorted_list2 if sublist[0] <= sp * (1 + spr)]

        return filtered_list1, filtered_list2
    except Exception as e:
        return None, None


def get_order_table_buy(l1, l3, limit=10):
    """
    :param l1: 现货买
    :param l2: 现货卖
    :param l3: 期货买
    :param l4: 期货卖
    :return:
    """
    table = "```\n"
    l1 = l1 if len(l1) < limit else l1[:limit]
    l3 = l3 if len(l3) < limit else l3[:limit]
    pl1 = max(len(str(sublist[0])) for sublist in l1) + 2 if len(l1) > 0 else 3
    pl3 = max(len(str(sublist[0])) for sublist in l3) + 2 if len(l3) > 0 else 3
    vl1 = max(len(str(sublist[1])) for sublist in l1) if len(l1) > 0 else 3
    vl3 = max(len(str(sublist[1])) for sublist in l3) if len(l3) > 0 else 3
    half1 = pl1 + vl1 + 1
    half3 = pl3 + vl3 + 1
    table += f"|现货买{' ' * (half1 - 5)}|期货买{' ' * (half3 - 5)}|\n"
    table += f"|{'-' * pl1}|{'-' * vl1}|{'-' * pl3}|{'-' * vl3}|\n"
    for i in range(limit):
        if (i + 1) > len(l1) and (i + 1) > len(l3):
            break
        if (i + 1) <= len(l1) and (i + 1) <= len(l3):
            v1 = f" {l1[i][0]}"
            t1 = f"{v1}{(pl1 - len(v1)) * ' '}"
            v2 = f" {int(l1[i][1] / 1000)}k"
            t2 = f"{v2}{(vl1 - len(v2)) * ' '}"
            v3 = f" {l3[i][0]}"
            t3 = f"{v3}{(pl3 - len(v3)) * ' '}"
            v4 = f" {int(l3[i][1] / 1000)}k"
            t4 = f"{v4}{(vl3 - len(v4)) * ' '}"
            table += f"|{t1}|{t2}|{t3}|{t4}|\n"
        elif len(l3) < (i + 1) <= len(l1):
            v1 = f" {l1[i][0]}"
            t1 = f"{v1}{(pl1 - len(v1)) * ' '}"
            v2 = f" {int(l1[i][1] / 1000)}k"
            t2 = f"{v2}{(vl1 - len(v2)) * ' '}"
            t3 = f"{'-' * pl3}"
            t4 = f"{'-' * vl3}"
            table += f"|{t1}|{t2}|{t3}|{t4}|\n"
        elif len(l1) < (i + 1) <= len(l3):
            t1 = f"{'-' * pl1}"
            t2 = f"{'-' * vl1}"
            v3 = f" {l3[i][0]}"
            t3 = f"{v3}{(pl3 - len(v3)) * ' '}"
            v4 = f" {int(l3[i][1] / 1000)}k"
            t4 = f"{v4}{(vl3 - len(v4)) * ' '}"
            table += f"|{t1}|{t2}|{t3}|{t4}|\n"
    table += "```\n"
    return table


def get_order_table_sell(l1, l3, limit=10):
    """
    :param l1: 现货买
    :param l2: 现货卖
    :param l3: 期货买
    :param l4: 期货卖
    :return:
    """
    table = "```\n"
    l1 = l1 if len(l1) < limit else l1[:limit]
    l3 = l3 if len(l3) < limit else l3[:limit]
    pl1 = max(len(str(sublist[0])) for sublist in l1) + 2 if len(l1) > 0 else 3
    pl3 = max(len(str(sublist[0])) for sublist in l3) + 2 if len(l3) > 0 else 3
    vl1 = max(len(str(sublist[1])) for sublist in l1) if len(l1) > 0 else 3
    vl3 = max(len(str(sublist[1])) for sublist in l3) if len(l3) > 0 else 3
    half1 = pl1 + vl1 + 1
    half3 = pl3 + vl3 + 1
    table += f"|现货卖{' ' * (half1 - 5)}|期货卖{' ' * (half3 - 5)}|\n"
    table += f"|{'-' * pl1}|{'-' * vl1}|{'-' * pl3}|{'-' * vl3}|\n"
    for i in range(limit):
        if (i + 1) > len(l1) and (i + 1) > len(l3):
            break
        if (i + 1) <= len(l1) and (i + 1) <= len(l3):
            v1 = f" {l1[i][0]}"
            t1 = f"{v1}{(pl1 - len(v1)) * ' '}"
            v2 = f" {int(l1[i][1] / 1000)}k"
            t2 = f"{v2}{(vl1 - len(v2)) * ' '}"
            v3 = f" {l3[i][0]}"
            t3 = f"{v3}{(pl3 - len(v3)) * ' '}"
            v4 = f" {int(l3[i][1] / 1000)}k"
            t4 = f"{v4}{(vl3 - len(v4)) * ' '}"
            table += f"|{t1}|{t2}|{t3}|{t4}|\n"
        elif len(l3) < (i + 1) <= len(l1):
            v1 = f" {l1[i][0]}"
            t1 = f"{v1}{(pl1 - len(v1)) * ' '}"
            v2 = f" {int(l1[i][1] / 1000)}k"
            t2 = f"{v2}{(vl1 - len(v2)) * ' '}"
            t3 = f"{'-' * pl3}"
            t4 = f"{'-' * vl3}"
            table += f"|{t1}|{t2}|{t3}|{t4}|\n"
        elif len(l1) < (i + 1) <= len(l3):
            t1 = f"{'-' * pl1}"
            t2 = f"{'-' * vl1}"
            v3 = f" {l3[i][0]}"
            t3 = f"{v3}{(pl3 - len(v3)) * ' '}"
            v4 = f" {int(l3[i][1] / 1000)}k"
            t4 = f"{v4}{(vl3 - len(v4)) * ' '}"
            table += f"|{t1}|{t2}|{t3}|{t4}|\n"
    table += "```\n"
    return table


def format_number(num):
    if abs(num) >= 1000000:
        return f"{num / 1000000:.2f}M"
    elif abs(num) >= 1000:
        return f"{num / 1000:.2f}K"
    else:
        return str(num)


def format_price(symbol, price):
    if symbol.startswith("1000") or symbol in symbol1000:
        return price * 1000
    else:
        return price


def get_net_rank_table(net_list, interval, m=15, r=30):
    res = f"`符号        近{interval}净流入值     24h价格变化`\n"
    for i, l in enumerate(net_list):
        line = f"`{i + 1}.{l[0]}"
        n1 = len(line)
        line += ' ' * (m - n1)
        line += format_number(float(l[1]))
        n2 = len(line)
        line += ' ' * (r - n2)
        line += f"{str(l[2])}%"
        line += '`\n'
        res += line
    return res


def get_future_price(symbol):
    para = {
        'symbol': symbol
    }
    price = float(um_futures_client.ticker_price(**para)['price'])
    if symbol.startswith("1000") or symbol in ['XECUSDT', 'LUNCUSDT', 'PEPEUSDT', 'SHIBUSDT', 'BONKUSDT', 'SATSUSDT',
                                               'RATSUSDT', 'FLOKIUSDT']:
        return price * 1000
    else:
        return price


def get_delta_rank_table(delta_list, interval, m=15, r=30):
    res = f"`符号        近{interval}净持仓值     24h价格变化`\n"
    for i, l in enumerate(delta_list):
        line = f"`{i + 1}.{l[0]}"
        n1 = len(line)
        line += ' ' * (m - n1)
        line += format_number(float(l[1]))
        n2 = len(line)
        line += ' ' * (r - n2)
        line += f"{str(l[2])}%"
        line += '`\n'
        res += line
    return res


def get_delta_diff_rank_table(delta_list, interval, m=15, r=30, b=40):
    res = f"`符号        近{interval}净持仓变化     变化比     24h价格变化`\n"
    for i, l in enumerate(delta_list):
        line = f"`{i + 1}.{l[0]}"
        n1 = len(line)
        line += ' ' * (m - n1)
        line += format_number(float(l[1]))
        n2 = len(line)
        line += ' ' * (r - n2)
        line += f"{str(l[2])}%"
        n3 = len(line)
        line += ' ' * (b - n3)
        line += f"{str(l[3])}%"
        line += '`\n'
        res += line
    return res


def get_symbol_oi_table(symbol_oi, m=10, r=24):
    res = f"`周期      净持仓值      持仓变化`\n"
    for i, l in enumerate(symbol_oi):
        line = f"`{l[0]}:"
        n1 = len(line)
        line += ' ' * (m - n1)
        line += format_number(float(l[1]))
        n2 = len(line)
        line += ' ' * (r - n2)
        if i == len(symbol_oi) - 1:
            diff = 'NA'
        else:
            before = float(symbol_oi[i + 1][1])
            diff = round((float(l[1]) - before) / abs(before) * 100, 0)
        line += f"{diff}%"
        line += '`\n'
        res += line
    return res


def get_symbol_nf_table(symbol_nf, m=10, k=22):
    res = f"`周期     期货净流入    现货净流入`\n"
    for i, l in enumerate(symbol_nf):
        line = f"`{l[0]}:"
        n1 = len(line)
        line += ' ' * (m - n1)
        if l[1]:
            line += format_number(float(l[1]))
        else:
            line += 'None'
        n2 = len(line)
        line += ' ' * (k - n2)
        if l[2]:
            line += format_number(float(l[2]))
        else:
            line += 'None'
        line += '`\n'
        res += line
    return res


def binance_future_list():
    params = {}
    future = um_futures_client.ticker_24hr_price_change(**params)
    if isinstance(future, list) and future:
        now_utc = datetime.datetime.now(timezone.utc)
        yesterday_utc = now_utc - timedelta(days=1)
        yesterday_timestamp_utc = int(yesterday_utc.timestamp()) * 1000
        symbols_future = set(
            [token['symbol'] for token in future
             if
             token['symbol'].endswith('USDT') and 'USDC' not in token['symbol'] and 'FDUSD' not in token['symbol'] and
             token['count'] != 0 and token['closeTime'] > yesterday_timestamp_utc])

        return symbols_future

    else:
        print("无数据或数据格式不正确")


def get_funding_rate(symbol):
    try:
        para = {
            'symbol': symbol,
            'limit': 1
        }
        data = um_futures_client.funding_rate(**para)
        fr = float(data[0]['fundingRate'])
        return [symbol, fr]
    except Exception as e:
        print(e)
        return 0


def get_funding_rate_info():
    fr_list = []
    future_list = binance_future_list()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交所有的 API 请求，并行运行 fetch_taker_data 函数
        futures = [executor.submit(get_funding_rate, symbol) for symbol in
                   future_list]

        # 等待所有任务完成，并收集结果
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                fr_list.append(result)

    # 按净成交量进行排序
    positive_count = sum(1 for v in fr_list if v[1] > 0)
    total_count = len(fr_list)
    percentage_positive = (positive_count / total_count) * 100 if total_count > 0 else 0
    percentage_negative = 100 - percentage_positive

    # 按value降序和升序排序，取前十
    sorted_descending = sorted(fr_list, key=lambda x: x[1], reverse=True)[:10]
    sorted_ascending = sorted(fr_list, key=lambda x: x[1])[:10]
    return round(percentage_positive, 2), round(percentage_negative, 2), sorted_descending, sorted_ascending


def get_funding_info_str():
    lr, sr, lt, st = get_funding_rate_info()
    res = f"🟢⚖️资金费率为正的比率：*{lr}%*\n🔴⚖️资金费率为负的比率：*{sr}%*\n"
    res += '\n'
    res += "📈🔝*高资金费率top10:*\n"
    for v in lt:
        symbol = v[0][:-4]
        n = len(symbol)
        res += f"{symbol}{' ' * (15 - n)}{v[1]}\n"
    res += '\n'
    res += "📉🔝*低资金费率top10:*\n"
    for v in st:
        symbol = v[0][:-4]
        n = len(symbol)
        res += f"{symbol}{' ' * (15 - n)}{v[1]}\n"
    return res
