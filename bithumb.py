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

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 检查 HTTP 状态码

        res = response.json()

        # 检查返回数据是否为列表
        if not isinstance(res, list):
            print(f"API 返回的不是列表: {res}")
            return "无法获取警报数据：API 返回格式错误"

        # 如果列表为空，返回提示
        if not res:
            return "当前没有虚拟资产警报"

        # 按 end_date 降序排序
        sorted_list = sorted(res, key=lambda x: x.get('end_date', ''), reverse=True)
        result = ""
        for item in sorted_list:
            # 验证 item 是字典且包含必要字段
            if not isinstance(item, dict) or "market" not in item or "warning_type" not in item or "end_date" not in item:
                print(f"跳过无效项: {item}")
                continue

            market = item["market"]
            warning_type = item["warning_type"]
            end_date = item["end_date"]

            # 确保 market 是字符串并包含 '-'
            if not isinstance(market, str) or '-' not in market:
                print(f"无效的 market 格式: {market}")
                continue

            token = market.split('-')[1]
            alert_message = alert_dict.get(warning_type, f"未知警报类型: {warning_type}")
            result += f"`{token}`产生警报：*{alert_message}* | 警报结束时间：{end_date}\n"

        return result if result else "没有有效的警报数据"

    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return f"无法获取警报数据：网络错误 - {str(e)}"
    except ValueError as e:
        print(f"JSON 解析失败: {e}")
        return "无法获取警报数据：JSON 解析错误"
    except Exception as e:
        print(f"未知错误: {e}")
        return f"无法获取警报数据：未知错误 - {str(e)}"


def get_bithumb_token_list(url="https://api.bithumb.com/v1/market/all?isDetails=false"):
    headers = {"accept": "application/json"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 检查 HTTP 状态码，如果不是 200 则抛出异常

        data = response.json()  # 解析 JSON 数据

        # 检查 'status' 是否为 '0000'（Bithumb API 的成功标志）
        if data.get("status") != "0000":
            print(f"API 返回错误，状态: {data.get('status')}")
            return None

        # 检查 'data' 是否存在且是列表
        token_data = data.get("data")
        if not isinstance(token_data, list):
            print(f"API 返回的 'data' 不是列表: {token_data}")
            return None

        token = []
        for item in token_data:
            # 确保 item 是字典且包含 'market' 键
            if not isinstance(item, dict) or "market" not in item:
                print(f"跳过无效项: {item}")
                continue
            market = item["market"]
            # 确保 market 是字符串并包含 '-'
            if isinstance(market, str) and "-" in market:
                token.append(market.split('-')[1])
            else:
                print(f"无效的 market 格式: {market}")

        # 去重并返回
        token = list(set(token))
        return token if token else None

    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None
    except ValueError as e:
        print(f"JSON 解析失败: {e}")
        return None
    except Exception as e:
        print(f"未知错误: {e}")
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

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 检查 HTTP 状态码

        res = response.json()

        # 检查返回数据是否为列表
        if not isinstance(res, list):
            print(f"API 返回的不是列表: {res}")
            return None

        r = []
        for item in res:
            # 验证 item 是字典且包含 'market' 和 'warning_type'
            if not isinstance(item, dict) or "market" not in item or "warning_type" not in item:
                print(f"跳过无效项: {item}")
                continue

            market = item["market"]
            warning_type = item["warning_type"]

            # 确保 market 是字符串并包含 '-'
            if not isinstance(market, str) or '-' not in market:
                print(f"无效的 market 格式: {market}")
                continue

            token = market.split('-')[1]
            if token == symbol:
                alert_message = alert_dict.get(warning_type, f"未知警报类型: {warning_type}")
                r.append(alert_message)

        # 根据结果返回
        return [1, r] if r else [0, 0]

    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None
    except ValueError as e:
        print(f"JSON 解析失败: {e}")
        return None
    except Exception as e:
        print(f"未知错误: {e}")
        return None