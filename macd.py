# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin
#    @Create Time   : 2025/6/4 18:07
#    @Description   : 检测价格和交易量MACD金叉的代码
#    @Modified      : 2025/7/28, 添加交易量MACD金叉检测
#
# ===============================================================
import ccxt
import pandas as pd
import pandas_ta as ta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 初始化交易所（以币安为例）
exchange = ccxt.binance({
    'enableRateLimit': True,
})


# 获取USDT交易对
def get_usdt_pairs():
    try:
        markets = exchange.load_markets()
        spot_pairs = set()
        futures_pairs = set()
        spot_base_coins = set()
        fil_str_list = ['USDC', 'FDUSD', 'TUSDUSDT', 'USDP', 'EUR', 'XUSD', 'USD1']

        for symbol, market in markets.items():
            if symbol.endswith('USDT') and market.get('active', False):
                if market.get('type') == 'spot' and market.get('spot', False):
                    base_coin = symbol.replace('/USDT', '')
                    if base_coin not in fil_str_list:
                        spot_pairs.add(symbol)
                    spot_base_coins.add(base_coin)
                elif market.get('contract', False) and market.get('linear', False):
                    futures_pairs.add(symbol)

        filtered_futures_pairs = set()
        for symbol in futures_pairs:
            base_coin = symbol.replace('/USDT:USDT', '')
            if base_coin not in spot_base_coins and base_coin not in fil_str_list:
                filtered_futures_pairs.add(symbol)

        usdt_pairs = sorted(list(spot_pairs | filtered_futures_pairs))
        logging.info(
            f"找到 {len(spot_pairs)} 个现货 USDT 交易对，"
            f"{len(futures_pairs)} 个合约 USDT 交易对，"
            f"{len(filtered_futures_pairs)} 个仅合约的 USDT 交易对，"
            f"总并集 {len(usdt_pairs)} 个"
        )
        return usdt_pairs
    except Exception as e:
        logging.error(f"获取交易对失败：{e}")
        return []


# 获取K线数据
def get_ohlcv(symbol, timeframe='1d', limit=100, market_type="spot"):
    try:
        params = {'type': 'future'} if market_type == 'futures' else {}
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, params=params, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df
    except Exception as e:
        logging.warning(f"获取 {symbol} 的 {timeframe} 数据失败：{e}")
        return None


# 检查MACD金叉（价格或交易量，增强筛选，添加KDJ和RSI）
def check_macd_golden_cross(df, timeframe='1d', data_type='price'):
    try:
        df = df.copy()
        # 选择输入数据：价格（close）或交易量（volume）
        data_column = 'close' if data_type == 'price' else 'volume'

        if not isinstance(df, pd.DataFrame) or data_column not in df.columns:
            logging.warning(f"{timeframe} {data_type} 输入必须是包含 '{data_column}' 列的 DataFrame")
            return False

        if len(df) < 35:
            logging.warning(f"{timeframe} {data_type} 数据不足：需要至少 35 条，当前有 {len(df)} 条")
            return False

        if df[data_column].isna().any():
            logging.warning(f"{timeframe} {data_type} 列包含缺失值")
            return False
        if not pd.api.types.is_numeric_dtype(df[data_column]):
            logging.warning(f"{timeframe} {data_type} 列包含非数值数据")
            return False

        # 计算MACD
        macd = ta.macd(df[data_column], fast=12, slow=26, signal=9)
        if macd is None or macd.empty:
            logging.warning(f"{timeframe} {data_type} MACD 计算失败")
            return False

        if 'MACD_12_26_9' not in macd.columns or 'MACDs_12_26_9' not in macd.columns:
            logging.warning(f"{timeframe} {data_type} MACD 计算结果缺少必要列")
            return False

        df['macd'] = macd['MACD_12_26_9']
        df['signal'] = macd['MACDs_12_26_9']
        df = df.dropna(subset=['macd', 'signal'])

        if len(df) < 2:
            logging.warning(f"{timeframe} {data_type} 清理 NaN 后数据不足：{len(df)} 条")
            return False

        # 判断金叉
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        is_golden_cross = prev['macd'] <= prev['signal'] and latest['macd'] > latest['signal']

        if is_golden_cross:
            # 交易量MACD无需检查交易量放大（自身已是交易量指标）
            if data_type == 'price':
                if len(df) >= 20:
                    recent_volume = df['volume'].iloc[-5:].mean()
                    past_volume = df['volume'].iloc[-20:-5].mean()
                    if recent_volume < past_volume * 1.1:
                        logging.info(f"{timeframe} 价格MACD金叉，成交量未放大，过滤")
                        return False

            # 计算KDJ
            if not all(col in df.columns for col in ['high', 'low']):
                logging.warning(f"{timeframe} 输入缺少 'high' 或 'low' 列，无法计算 KDJ")
                return False
            kdj = ta.kdj(df['high'], df['low'], df['close'], length=14, signal=5)
            if kdj is None or kdj.empty:
                logging.warning(f"{timeframe} KDJ 计算失败")
                return False
            if kdj['K_14_5'].isna().any() or kdj['D_14_5'].isna().any():
                df['kdj_k'] = kdj['K_14_5']
                df['kdj_d'] = kdj['D_14_5']
                df = df.dropna(subset=['kdj_k', 'kdj_d'])
                if len(df) < 3:
                    logging.warning(f"{timeframe} 清理 KDJ NaN 后数据不足：{len(df)} 条")
                    return False
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                is_golden_cross = prev['macd'] <= prev['signal'] and latest['macd'] > latest['signal']
                if not is_golden_cross:
                    logging.info(f"{timeframe} {data_type} 清理 KDJ NaN 后 MACD 金叉失效")
                    return False
            else:
                df['kdj_k'] = kdj['K_14_5']
                df['kdj_d'] = kdj['D_14_5']

            # KDJ看涨条件
            prev_2 = df.iloc[-3]
            is_kdj_bullish = latest['kdj_k'] > latest['kdj_d'] or \
                             (prev['kdj_k'] <= prev['kdj_d'] and latest['kdj_k'] > latest['kdj_d']) or \
                             (prev_2['kdj_k'] <= prev_2['kdj_d'] and prev['kdj_k'] > prev['kdj_d'])
            if not is_kdj_bullish:
                logging.info(f"{timeframe} {data_type} KDJ 非看涨状态，过滤")
                return False
            if latest['kdj_k'] > 80 or latest['kdj_d'] > 80:
                logging.info(f"{timeframe} {data_type} KDJ 超买（K={latest['kdj_k']:.2f}, D={latest['kdj_d']:.2f}），过滤")
                return False
            if latest['kdj_k'] < 20:
                logging.info(f"{timeframe} {data_type} KDJ 超卖（K={latest['kdj_k']:.2f}），可能低位反弹")

            # 计算RSI（基于价格）
            rsi = ta.rsi(df['close'], length=14)
            if rsi is None or rsi.empty:
                logging.warning(f"{timeframe} RSI 计算失败")
                return False
            if rsi.isna().any():
                df['rsi'] = rsi
                df = df.dropna(subset=['rsi'])
                if len(df) < 2:
                    logging.warning(f"{timeframe} 清理 RSI NaN 后数据不足：{len(df)} 条")
                    return False
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                is_golden_cross = prev['macd'] <= prev['signal'] and latest['macd'] > latest['signal']
                if not is_golden_cross:
                    logging.info(f"{timeframe} {data_type} 清理 RSI NaN 后金叉失效")
                    return False
            else:
                df['rsi'] = rsi

            if latest['rsi'] > 70:
                logging.info(f"{timeframe} {data_type} RSI 超买（{latest['rsi']:.2f}），过滤")
                return False

            logging.info(
                f"{timeframe} {data_type} 检测到优质金叉：MACD={latest['macd']:.4f} > Signal={latest['signal']:.4f}, "
                f"KDJ K={latest['kdj_k']:.2f}, D={latest['kdj_d']:.2f}, RSI={latest['rsi']:.2f}")
            return is_golden_cross
        return False
    except Exception as e:
        logging.warning(f"{timeframe} {data_type} 发生错误：{e}")
        return False


# 处理单个币种（价格和交易量MACD）
def process_symbol(symbol):
    try:
        logging.debug(f"开始处理 {symbol}")
        market = exchange.load_markets()[symbol]
        market_type = 'futures' if market.get('contract', False) and market.get('linear', False) else 'spot'
        # 获取1W、1D、4H、1H数据
        df_1w = get_ohlcv(symbol, timeframe='1w', limit=100, market_type=market_type)
        df_1d = get_ohlcv(symbol, timeframe='1d', limit=100, market_type=market_type)
        df_4h = get_ohlcv(symbol, timeframe='4h', limit=100, market_type=market_type)
        df_1h = get_ohlcv(symbol, timeframe='1h', limit=100, market_type=market_type)

        if any(df is None or df.empty for df in [df_1w, df_1d, df_4h, df_1h]):
            logging.warning(f"{symbol} 的某些时间框架数据无效")
            return None

        # 检查价格和交易量MACD金叉
        res = {'symbol': symbol.split("/")[0], 'price': {}, 'volume': {}}
        for timeframe, df in [('1w', df_1w), ('1d', df_1d), ('4h', df_4h), ('1h', df_1h)]:
            res['price'][timeframe] = check_macd_golden_cross(df, timeframe, data_type='price')
            res['volume'][timeframe] = check_macd_golden_cross(df, timeframe, data_type='volume')
        return res
    except Exception as e:
        logging.warning(f"处理 {symbol} 失败：{e}")
        return None


# 主程序（并行扫描价格和交易量MACD金叉）
def find_macd_golden_cross_coins(max_workers=10):
    start_time = time.time()
    logging.info("正在扫描价格和交易量MACD金叉的潜力币种...")
    results = {'price': {'1w': [], '1d': [], '4h': [], '1h': []}, 'volume': {'1w': [], '1d': [], '4h': [], '1h': []}}

    symbols = get_usdt_pairs()
    logging.info(f"共找到 {len(symbols)} 个活跃USDT交易对")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {executor.submit(process_symbol, symbol): symbol for symbol in symbols}
        for future in as_completed(future_to_symbol):
            result = future.result()
            if result:
                for timeframe in ['1w', '1d', '4h', '1h']:
                    if result['price'][timeframe]:
                        results['price'][timeframe].append(result['symbol'])
                    if result['volume'][timeframe]:
                        results['volume'][timeframe].append(result['symbol'])

    elapsed_time = time.time() - start_time
    logging.info(f"扫描完成，耗时 {elapsed_time:.2f} 秒")
    return results


# 输出结果
def get_macd_str():
    results = find_macd_golden_cross_coins()
    res = ""

    # 价格MACD金叉
    for timeframe in ['1w', '1d', '4h', '1h']:
        if results['price'][timeframe]:
            res += f"\n\n✨📣*发现以下币种在 {timeframe.upper()} 价格MACD金叉：*"
            for coin in results['price'][timeframe]:
                res += f"\n`{coin}`"
        else:
            res += f"\n\n✨🔇*未发现 {timeframe.upper()} 价格MACD金叉的币种*"

    # 交易量MACD金叉
    for timeframe in ['1w', '1d', '4h', '1h']:
        if results['volume'][timeframe]:
            res += f"\n\n✨📣*发现以下币种在 {timeframe.upper()} 交易量MACD金叉：*"
            for coin in results['volume'][timeframe]:
                res += f"\n`{coin}`"
        else:
            res += f"\n\n✨🔇*未发现 {timeframe.upper()} 交易量MACD金叉的币种*"

    return res
