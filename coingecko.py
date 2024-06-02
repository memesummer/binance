import requests


def get_gecko_token_id_by_symbol(symbol):
    base_url = "https://api.coingecko.com/api/v3"
    endpoint = "/coins/list"

    try:
        response = requests.get(f"{base_url}{endpoint}")
        data = response.json()

        # 检查是否成功获取数据
        if response.status_code == 200:
            for token in data:
                if token['symbol'].lower() == symbol.lower():
                    return token['id']
            print(f"Token with symbol {symbol} not found.")
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
    except requests.RequestException as e:
        print(f"Error making request: {e}")

    return None


def get_gecko_token_info_by_symbol(symbol, vs_currency="usd"):
    base_url = "https://api.coingecko.com/api/v3"
    endpoint = "/coins/markets"

    params = {
        "vs_currency": vs_currency,
        "ids": symbol,
    }

    try:
        response = requests.get(f"{base_url}{endpoint}", params=params)
        data = response.json()

        # 检查是否成功获取数据
        if response.status_code == 200 and len(data) > 0:
            if isinstance(data, list):  # 如果返回的是列表
                token_info = data[0]
            else:
                token_info = data
            return token_info
        else:
            print(f"Failed to fetch data for {symbol}. Status code: {response.status_code}")
            print(f"Error message: {data}")
    except requests.RequestException as e:
        print(f"Error making request: {e}")

    return None, None


def get_cmc(symbol):
    token_id = get_gecko_token_id_by_symbol(symbol)
    token_info = get_gecko_token_info_by_symbol(token_id)
    cmc = token_info['market_cap']
    print(cmc)
    return cmc


