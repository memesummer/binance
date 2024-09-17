# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2024/5/29 14:43
#    @Description   : 
#
# ==============================================================
from binance.um_futures import UMFutures
from main import binance_api_get, get_latest_price

um_futures_client = UMFutures()


def get_future_pending_order_rank(symbol, order_value, limit=1000, bpr=0.1, spr=0.1):
    try:
        para = {
            'symbol': symbol,
            'limit': limit
        }
        data = um_futures_client.depth(**para)
        fp = float(get_future_price(symbol))

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


def get_net_rank_table(net_list, interval, m=15, r=30):
    res = f"`符号        近{interval}净流入值(w)  24h价格变化`\n"
    for i, l in enumerate(net_list):
        line = f"`{i + 1}.{l[0]}"
        n1 = len(line)
        line += ' ' * (m - n1)
        line += str(l[1])
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
    price = um_futures_client.ticker_price(**para)['price']
    return price


def get_delta_rank_table(delta_list, interval, m=15, r=30):
    res = f"`符号        近{interval}净持仓值(w)  24h价格变化`\n"
    for i, l in enumerate(delta_list):
        line = f"`{i + 1}.{l[0]}"
        n1 = len(line)
        line += ' ' * (m - n1)
        line += str(l[1])
        n2 = len(line)
        line += ' ' * (r - n2)
        line += f"{str(l[2])}%"
        line += '`\n'
        res += line
    return res


def get_symbol_oi_table(symbol_oi, m=10):
    res = f"`周期     净持仓值(w)`\n"
    for i, l in enumerate(symbol_oi):
        line = f"`{l[0]}:"
        n1 = len(line)
        line += ' ' * (m - n1)
        line += str(l[1])
        # n2 = len(line)
        # line += ' ' * (r - n2)
        # line += f"{str(l[2])}%"
        line += '`\n'
        res += line
    return res

# para = {
#     'symbol': 'TNSRUSDT'
# }
# a = um_futures_client.agg_trades(**para)
# res = 0
# for d in a:
#     if float(d['p']) * float(d['q']) >= 500000:
#         res += 1
# print(res)

# a, b, c, d = get_future_takerlongshortRatio('BTCUSDT')
# print(a)
# print(b)
# print(c)
# print(d)
