"""Crypto.com Exchange public market data and PAPER-ONLY strategy helpers."""
import requests
import pandas as pd

BASE = 'https://api.crypto.com/exchange/v1'
ASSETS = ('BTC', 'ETH', 'SOL', 'ADA', 'XRP')
FEE = 0.001  # Hypothèse pédagogique, pas les frais réels de l'utilisateur.

class MarketError(Exception):
    pass

def _get(method, params=None):
    try:
        response = requests.get(f'{BASE}/public/{method}', params=params, timeout=15,
                                headers={'Accept': 'application/json', 'User-Agent': 'CryptoAIV7-paper/1.0'})
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise MarketError(f'API Crypto.com indisponible : {exc}') from exc
    if str(payload.get('code', -1)) != '0':
        raise MarketError(f"Crypto.com : {payload.get('message', 'erreur API')} (code {payload.get('code')})")
    return payload.get('result', {})

def spot_pairs():
    """Select actual spot USDT instruments, never derivatives or margin."""
    data = _get('get-instruments').get('data', [])
    selected = {}
    for item in data:
        base = item.get('base_ccy')
        quote = item.get('quote_ccy')
        kind = str(item.get('inst_type', '')).upper()
        name = item.get('symbol') or item.get('instrument_name')
        if base in ASSETS and quote == 'USDT' and kind == 'SPOT' and name and item.get('tradable', True) is not False:
            selected[base] = name
    return selected

def tickers(pairs):
    if not pairs:
        return {}
    rows = _get('get-tickers').get('data', [])
    by_name = {r.get('i'): r for r in rows}
    output = {}
    for asset, name in pairs.items():
        row = by_name.get(name)
        if row:
            try:
                price = float(row['a'])
                change = float(row.get('c') or 0) * 100
                if price > 0:
                    output[asset] = {'pair': name, 'price': price, 'change': change,
                                     'timestamp': pd.to_datetime(int(row['t']), unit='ms', utc=True) if row.get('t') else None}
            except (ValueError, TypeError, KeyError):
                continue
    return output

def history(pair, days=90):
    result = _get('get-candlestick', {'instrument_name': pair, 'timeframe': '1D', 'count': days + 45})
    rows = result.get('data', [])
    if not rows:
        raise MarketError('Aucune bougie historique retournée pour cette paire.')
    frame = pd.DataFrame(rows)
    try:
        frame['date'] = pd.to_datetime(pd.to_numeric(frame['t']), unit='ms', utc=True)
        frame['close'] = pd.to_numeric(frame['c'], errors='coerce')
    except (KeyError, ValueError) as exc:
        raise MarketError('Format des bougies inattendu.') from exc
    series = frame.dropna(subset=['close']).set_index('date')['close'].sort_index()
    series = series[~series.index.duplicated(keep='last')]
    series = series[series > 0]
    if len(series) < 40:
        raise MarketError('Historique insuffisant (moins de 40 bougies).')
    return series.tail(days + 35)

def indicators(series):
    s = series.astype(float)
    delta = s.diff()
    up = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = up / down.replace(0, float('nan'))
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.mask((down == 0) & (up > 0), 100).mask((down == 0) & (up == 0), 50)
    macd = s.ewm(span=12, adjust=False).mean() - s.ewm(span=26, adjust=False).mean()
    return pd.DataFrame({'Cours': s, 'SMA10': s.rolling(10).mean(), 'SMA30': s.rolling(30).mean(),
                         'RSI': rsi, 'MACD': macd, 'Signal MACD': macd.ewm(span=9, adjust=False).mean()})

def decision(row, strategy):
    if pd.isna(row['SMA30']) or pd.isna(row['RSI']):
        return 'ATTENDRE'
    if strategy == 'Tendance + MACD':
        if row['SMA10'] > row['SMA30'] and row['MACD'] > row['Signal MACD'] and row['RSI'] < 70:
            return 'ACHETER'
        if row['SMA10'] < row['SMA30'] or row['RSI'] > 75:
            return 'VENDRE'
    else:
        if row['SMA10'] > row['SMA30'] and row['RSI'] < 65:
            return 'ACHETER'
        if row['SMA10'] < row['SMA30'] or row['RSI'] > 75:
            return 'VENDRE'
    return 'CONSERVER'

def backtest(series, strategy, days=90, initial=10000.0):
    """Signals at previous close, trades at next close; simplified, no slippage."""
    frame = indicators(series)
    cash, units = float(initial), 0.0
    curve, orders = [], []
    start = max(30, len(frame) - days)
    for i in range(start, len(frame)):
        signal = decision(frame.iloc[i - 1], strategy)
        price = float(frame['Cours'].iloc[i])
        date = frame.index[i]
        if signal == 'ACHETER' and units == 0 and cash > 0:
            units = cash * (1 - FEE) / price
            orders.append({'Date': date.date().isoformat(), 'Action': 'ACHAT', 'Prix USDT': round(price, 5)})
            cash = 0.0
        elif signal == 'VENDRE' and units > 0:
            cash = units * price * (1 - FEE)
            units = 0.0
            orders.append({'Date': date.date().isoformat(), 'Action': 'VENTE', 'Prix USDT': round(price, 5)})
        curve.append((date, cash + units * price))
    if not curve:
        raise MarketError('Historique trop court pour le backtest.')
    values = pd.Series({d: v for d, v in curve}, name=strategy)
    reference = frame['Cours'].iloc[start:]
    hold = (reference / reference.iloc[0]) * initial
    perf = (values.iloc[-1] / initial - 1) * 100
    drawdown = ((values / values.cummax()) - 1).min() * 100
    return values, hold.rename('Achat-conservation'), perf, drawdown, orders
