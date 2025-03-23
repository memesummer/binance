# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2025/3/22 17:48
#    @Description   : 
#
# ===============================================================
import requests


def bithumb_alert():
    url = "https://api.bithumb.com/v1/market/virtual_asset_warning"
    alert_dict = {
        'PRICE_SUDDEN_FLUCTUATION': '价格波动',
        'TRADING_VOLUME_SUDDEN_FLUCTUATION': '交易量激增',
        'DEPOSIT_AMOUNT_SUDDEN_FLUCTUATION': '存款金额激增',
        'PRICE_DIFFERENCE_HIGH': '价格差异大',
        'SPECIFIC_ACCOUNT_HIGH_TRANSACTION': '特定账户高频交易',
        'EXCHANGE_TRADING_CONCENTRATION': '交易所交易焦点'
    }
    headers = {"accept": "application/json"}

    response = requests.get(url, headers=headers)

    res = response.json()
    sorted_list = sorted(res, key=lambda x: x['end_date'], reverse=True)
    res = ""
    for item in sorted_list:
        res += f"`{item['market'].split('-')[1]}`产生警报：*{alert_dict.get(item['warning_type'])}* | 警报结束时间：{item['end_date']}\n"
    return res


def get_bithumb_token_list(url="https://api.bithumb.com/v1/market/all?isDetails=false"):
    headers = {"accept": "application/json"}

    response = requests.get(url, headers=headers)

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
        print(f"get_bithumb_token_list请求失败，状态码: {response.status_code}")
        return None


def to_list_on_bithumb():
    from main import binance_spot_list, binance_future_list
    binance = list(set(list(binance_future_list()) + list(binance_spot_list())))
    upbit = get_bithumb_token_list()
    difference = [item[:-4] for item in binance if item[:-4] not in upbit]
    cleaned_difference = list(filter(bool, difference))
    return cleaned_difference


def is_on_alert(symbol):
    url = "https://api.bithumb.com/v1/market/virtual_asset_warning"
    alert_dict = {
        'PRICE_SUDDEN_FLUCTUATION': '价格突然波动',
        'TRADING_VOLUME_SUDDEN_FLUCTUATION': '交易量激增',
        'DEPOSIT_AMOUNT_SUDDEN_FLUCTUATION': 'CEX存款激增',
        'PRICE_DIFFERENCE_HIGH': '价格差异大',
        'SPECIFIC_ACCOUNT_HIGH_TRANSACTION': '特定账户高频交易',
        'EXCHANGE_TRADING_CONCENTRATION': 'CEX交易集中'
    }
    headers = {"accept": "application/json"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        res = response.json()
        r = []
        for item in res:
            if item['market'].split('-')[1] == symbol:
                r.append(alert_dict.get(item['warning_type']))
        if len(r) == 0:
            return [0, 0]
        else:
            return [1, r]
    else:
        print(f"is_on_alert请求失败，状态码: {response.status_code}")
        return None
