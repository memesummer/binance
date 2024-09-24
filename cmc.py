import json
import os

import requests


def get_cmc(symbol, api_key="dcb49ec3-0e14-4e3f-824c-3fb3ec40a46e"):
    base_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

    params = {
        'convert': 'USD',
        'CMC_PRO_API_KEY': api_key,
        'limit': 1000
    }

    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if response.status_code == 200:
            # 查找符号匹配的代币
            for token_info in data['data']:
                if token_info['symbol'].lower() == symbol.lower():
                    market_cap = token_info['quote']['USD']['market_cap']
                    return market_cap

            print(f"Symbol {symbol} not found in the data.")
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            print(f"Error message: {data.get('status', {}).get('error_message', 'No error message provided')}")
    except requests.RequestException as e:
        print(f"Error making request: {e}")

    return None


def save_circulating_supply(save_file, api_key="dcb49ec3-0e14-4e3f-824c-3fb3ec40a46e"):
    base_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

    params = {
        'convert': 'USD',
        'CMC_PRO_API_KEY': api_key,
        'limit': 2000
    }

    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if response.status_code == 200:
            # 查找符号匹配的代币
            with open(save_file, 'w', encoding='utf-8') as file:
                for token_info in data['data']:
                    symbol = token_info['symbol'].lower()
                    circulating_supply = token_info['circulating_supply']
                    if symbol == 'quick' and circulating_supply < 728513:
                        continue
                    if symbol == 'beam':
                        symbol = 'beamx'
                    file.write(f"{symbol}\t{circulating_supply}\n")
            print(f"流通量已成功保存到circulating.txt")
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            print(f"Error message: {data.get('status', {}).get('error_message', 'No error message provided')}")
    except requests.RequestException as e:
        print(f"Error making request: {e}")

    return None


def save_token_info(save_file, api_key="dcb49ec3-0e14-4e3f-824c-3fb3ec40a46e"):
    base_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

    params = {
        'convert': 'USD',
        'CMC_PRO_API_KEY': api_key,
        'limit': 5000
    }

    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if response.status_code == 200:
            # 查找符号匹配的代币
            # 将 JSON 数据写入文件
            with open(save_file, 'w', encoding='utf-8') as json_file:
                json.dump(data, json_file, ensure_ascii=False, indent=4)
            print(f"所有币信息已成功保存到token.json")
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            print(f"Error message: {data.get('status', {}).get('error_message', 'No error message provided')}")
    except requests.RequestException as e:
        print(f"Error making request: {e}")

    return None


# 获取当前脚本所在的目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 构建 circulating.txt 的绝对路径
circulating_file_path = os.path.join(current_dir, "circulating.txt")
token_info_file_path = os.path.join(current_dir, "token_data.json")
save_circulating_supply(circulating_file_path)
save_token_info(token_info_file_path)
