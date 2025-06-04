# -*- coding: utf-8 -*-
# ===============================================================
#
#    @Create Author : daixin 
#    @Create Time   : 2025/6/4 18:07
#    @Description   : 
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


def get_usdt_pairs():
    try:
        markets = exchange.load_markets()
        spot_pairs = set()
        futures_pairs = set()
        spot_base_coins = set()  # 用于存储现货市场的基础币
        fil_str_list = ['USDC', 'FDUSD', 'TUSDUSDT', 'USDP', 'EUR', 'XUSD', 'USD1']

        for symbol, market in markets.items():
            if symbol.endswith('USDT') and market.get('active', False):
                if market.get('type') == 'spot' and market.get('spot', False):
                    # 提取基础币（如 BTC/USDT -> BTC）
                    base_coin = symbol.replace('/USDT', '')
                    if base_coin not in fil_str_list:
                        spot_pairs.add(symbol)
                    spot_base_coins.add(base_coin)
                elif market.get('contract', False) and market.get('linear', False):
                    # 仅包括 USDT-M 永续合约
                    futures_pairs.add(symbol)

        # 过滤合约交易对，只保留基础币不在现货市场的交易对
        filtered_futures_pairs = set()
        for symbol in futures_pairs:
            base_coin = symbol.replace('/USDT:USDT', '')
            if base_coin not in spot_base_coins and base_coin not in fil_str_list:
                filtered_futures_pairs.add(symbol)

        # 取现货交易对和过滤后的合约交易对的并集并去重
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
        return df
    except Exception as e:
        logging.warning(f"获取 {symbol} 的 {timeframe} 数据失败：{e}")
        return None


# 检查 MACD 金叉（增强筛选，添加 KDJ）
def check_macd_golden_cross(df, timeframe='1d'):
    try:
        # 1. 确保 df 是副本，避免视图/副本警告
        df = df.copy()

        # 2. 检查输入数据
        if not isinstance(df, pd.DataFrame) or 'close' not in df.columns:
            logging.warning(f"{timeframe} 输入必须是包含 'close' 列的 DataFrame")
            return False

        # 3. 检查数据量（MACD 需要 35 条，RSI 需要 14 条）
        if len(df) < 35:
            logging.warning(f"{timeframe} 数据不足：需要至少 35 条，当前有 {len(df)} 条")
            return False

        # 4. 检查 close 列是否有缺失值或非数值
        if df['close'].isna().any():
            logging.warning(f"{timeframe} close 列包含缺失值")
            return False
        if not pd.api.types.is_numeric_dtype(df['close']):
            logging.warning(f"{timeframe} close 列包含非数值数据")
            return False

        # 5. 计算 MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is None or macd.empty:
            logging.warning(f"{timeframe} MACD 计算失败")
            return False

        if 'MACD_12_26_9' not in macd.columns or 'MACDs_12_26_9' not in macd.columns:
            logging.warning(f"{timeframe} MACD 计算结果缺少必要列")
            return False

        df['macd'] = macd['MACD_12_26_9']
        df['signal'] = macd['MACDs_12_26_9']
        df = df.dropna(subset=['macd', 'signal'])

        if len(df) < 2:
            logging.warning(f"{timeframe} 清理 NaN 后数据不足：{len(df)} 条")
            return False

        # 6. 判断金叉
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        is_golden_cross = prev['macd'] <= prev['signal'] and latest['macd'] > latest['signal']

        if is_golden_cross:
            # # 7. 增强筛选：要求金叉在零线上方
            # if latest['macd'] <= 0:
            #     logging.info(f"{timeframe} 金叉在零线下方，过滤")
            #     return False

            # 8. 检查交易量放大（最近 5 周期均值 > 前 20 周期均值）
            if len(df) >= 20:
                recent_volume = df['volume'].iloc[-5:].mean()
                past_volume = df['volume'].iloc[-20:-5].mean()
                if recent_volume < past_volume * 1.1:
                    logging.info(f"{timeframe} 成交量未放大，过滤")
                    return False

            # 9. 计算 KDJ
            if not all(col in df.columns for col in ['high', 'low']):
                logging.warning(f"{timeframe} 输入缺少 'high' 或 'low' 列，无法计算 KDJ")
                return False
            kdj = ta.kdj(df['high'], df['low'], df['close'], length=14, signal=5)
            if kdj is None or kdj.empty:
                logging.warning(f"{timeframe} KDJ 计算失败")
                return False
            if kdj[f'K_14_5'].isna().any() or kdj[f'D_14_5'].isna().any():
                logging.warning(f"{timeframe} KDJ 包含 NaN")
                logging.debug(f"{timeframe} close 数据最后 10 条：\n{df['close'].tail(10)}")
                df['kdj_k'] = kdj[f'K_14_5']
                df['kdj_d'] = kdj[f'D_14_5']
                df = df.dropna(subset=['kdj_k', 'kdj_d'])
                if len(df) < 3:  # 需要至少 3 条数据检查前周期
                    logging.warning(f"{timeframe} 清理 KDJ NaN 后数据不足：{len(df)} 条")
                    return False
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                is_golden_cross = prev['macd'] <= prev['signal'] and latest['macd'] > latest['signal']
                if not is_golden_cross:
                    logging.info(f"{timeframe} 清理 KDJ NaN 后 MACD 金叉失效")
                    return False
            else:
                df['kdj_k'] = kdj[f'K_14_5']
                df['kdj_d'] = kdj[f'D_14_5']

            # KDJ 看涨（K > D 或前 2 周期金叉）
            prev_2 = df.iloc[-3]
            is_kdj_bullish = latest['kdj_k'] > latest['kdj_d'] or \
                             (prev['kdj_k'] <= prev['kdj_d'] and latest['kdj_k'] > latest['kdj_d']) or \
                             (prev_2['kdj_k'] <= prev_2['kdj_d'] and prev['kdj_k'] > prev['kdj_d'])
            if not is_kdj_bullish:
                logging.info(f"{timeframe} KDJ 非看涨状态，过滤")
                return False
            if latest['kdj_k'] > 80 or latest['kdj_d'] > 80:
                logging.info(f"{timeframe} KDJ 超买（K={latest['kdj_k']:.2f}, D={latest['kdj_d']:.2f}），过滤")
                return False
            if latest['kdj_k'] < 20:
                logging.info(f"{timeframe} KDJ 超卖（K={latest['kdj_k']:.2f}），可能低位反弹")

            # 10. 计算 RSI
            rsi = ta.rsi(df['close'], length=14)
            if rsi is None or rsi.empty:
                logging.warning(f"{timeframe} RSI 计算失败，可能是数据不足或异常")
                return False
            if rsi.isna().any():
                # 尝试清理 RSI 的 NaN，仅保留有效数据
                df['rsi'] = rsi
                df = df.dropna(subset=['rsi'])
                if len(df) < 2:
                    logging.warning(f"{timeframe} 清理 RSI NaN 后数据不足：{len(df)} 条")
                    return False
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                # 重新检查金叉（清理后可能影响索引）
                is_golden_cross = prev['macd'] <= prev['signal'] and latest['macd'] > latest['signal']
                if not is_golden_cross:
                    logging.info(f"{timeframe} 清理 RSI NaN 后金叉失效")
                    return False
            else:
                df['rsi'] = rsi

            # 11. RSI 超买检查
            if latest['rsi'] > 70:
                logging.info(f"{timeframe} RSI 超买（{latest['rsi']:.2f}），过滤")
                return False

            logging.info(
                f"{timeframe} 检测到优质金叉：MACD={latest['macd']:.4f} > Signal={latest['signal']:.4f}, KDJ K={latest['kdj_k']:.2f}, D={latest['kdj_d']:.2f}, RSI={latest['rsi']:.2f}")
        return is_golden_cross

    except Exception as e:
        logging.warning(f"{timeframe} 发生错误：{e}")
        return False

    except Exception as e:
        logging.warning(f"{timeframe} 发生错误：{e}")
        return False


# 处理单个币种
def process_symbol(symbol):
    try:
        logging.debug(f"开始处理 {symbol}")
        market = exchange.load_markets()[symbol]
        market_type = 'futures' if market.get('contract', False) and market.get('linear', False) else 'spot'
        # 获取 1D、4H、1H 数据
        df_1w = get_ohlcv(symbol, timeframe='1w', limit=100, market_type=market_type)
        df_1d = get_ohlcv(symbol, timeframe='1d', limit=100, market_type=market_type)
        df_4h = get_ohlcv(symbol, timeframe='4h', limit=100, market_type=market_type)
        df_1h = get_ohlcv(symbol, timeframe='1h', limit=100, market_type=market_type)

        if any(df is None or df.empty for df in [df_4h]):
            logging.warning(f"{symbol} 的某些时间框架数据无效")
            return None

        # 检查所有时间框架的 MACD 金叉
        golden_cross_1w = check_macd_golden_cross(df_1w, timeframe='1w')
        golden_cross_1d = check_macd_golden_cross(df_1d, timeframe='1d')
        golden_cross_4h = check_macd_golden_cross(df_4h, timeframe='4h')
        golden_cross_1h = check_macd_golden_cross(df_1h, timeframe='1h')

        res = []

        symbol = symbol.split("/")[0]

        if golden_cross_1w:
            res.append(symbol)
        else:
            res.append('None')
        if golden_cross_1d:
            res.append(symbol)
        else:
            res.append('None')
        if golden_cross_4h:
            res.append(symbol)
        else:
            res.append('None')
        if golden_cross_1h:
            res.append(symbol)
        else:
            res.append('None')
        return res
    except Exception as e:
        logging.warning(f"处理 {symbol} 失败：{e}")
        return None


# 主程序（并行版本）
def find_macd_golden_cross_coins(max_workers=10):
    start_time = time.time()
    logging.info("正在扫描 1D、4H、1H MACD金叉的潜力币种...")
    golden_cross_coins_1w = []
    golden_cross_coins_1d = []
    golden_cross_coins_4h = []
    golden_cross_coins_1h = []

    symbols = get_usdt_pairs()
    logging.info(f"共找到 {len(symbols)} 个活跃USDT交易对")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {executor.submit(process_symbol, symbol): symbol for symbol in symbols}
        for future in as_completed(future_to_symbol):
            result = future.result()
            if result:
                if result[0] != "None":
                    golden_cross_coins_1w.append(result[0])
                if result[1] != "None":
                    golden_cross_coins_1d.append(result[1])
                if result[2] != "None":
                    golden_cross_coins_4h.append(result[2])
                if result[3] != "None":
                    golden_cross_coins_1h.append(result[3])

    elapsed_time = time.time() - start_time
    logging.info(f"扫描完成，耗时 {elapsed_time:.2f} 秒")
    return golden_cross_coins_1w, golden_cross_coins_1d, golden_cross_coins_4h, golden_cross_coins_1h


# 执行程序
def get_macd_str():
    g1w, g1d, g4h, g1h = find_macd_golden_cross_coins()
    res = ""
    if g1w:
        res += "✨📣*发现以下币种在 1W 出现优质MACD金叉：*"
        for coin in g1w:
            res += f"\n`{coin}`"
    else:
        res += "\n\n✨🔇*未发现 1W 优质MACD金叉的币种*"
    if g1d:
        res += "\n\n✨📣*发现以下币种在 1D 出现优质MACD金叉：*"
        for coin in g1d:
            res += f"\n`{coin}`"
    else:
        res += "\n\n✨🔇*未发现 1D 优质MACD金叉的币种*"

    if g4h:
        res += "\n\n✨📣*发现以下币种在 4H 出现优质MACD金叉：*"
        for coin in g4h:
            res += f"\n`{coin}`"
    else:
        res += "\n\n✨🔇*未发现 4H 优质MACD金叉的币种*"

    if g1h:
        res += "\n\n✨📣*发现以下币种在 1H 出现优质MACD金叉：*"
        for coin in g1h:
            res += f"\n`{coin}`"
    else:
        res += "\n\n✨🔇*未发现 1H 优质MACD金叉的币种*"
    return res
