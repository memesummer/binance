import requests


def get_tokeninfo(symbol, api_key="dcb49ec3-0e14-4e3f-824c-3fb3ec40a46e"):
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
                    return token_info

            print(f"Symbol {symbol} not found in the data.")
        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            print(f"Error message: {data.get('status', {}).get('error_message', 'No error message provided')}")
    except requests.RequestException as e:
        print(f"Error making request: {e}")

    return None


print('btc')
