"""Crypto AI V6: public market data and simulation-only trading logic."""
import time
import requests
import pandas as pd
import numpy as np

COINS = {"BTC": ("bitcoin", "Bitcoin"), "ETH": ("ethereum", "Ethereum"), "SOL": ("solana", "Solana"), "ADA": ("cardano", "Cardano"), "XRP": ("ripple", "XRP")}
BASE = "https://api.coingecko.com/api/v3"
HEADERS = {"accept": "application/json", "User-Agent": "CryptoAIV6Educational/1.0"}

class MarketDataError(Exception):
    pass

def api_get(path, params):
    try:
        response = requests.get(f"{BASE}{path}", params=params, headers=HEADERS, timeout=20)
        if response.status_code == 429:
            raise MarketDataError("CoinGecko limite les requêtes (HTTP 429). Attends quelques minutes avant de réessayer.")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise MarketDataError(f"Connexion CoinGecko indisponible : {exc}") from exc
    except ValueError as exc:
        raise MarketDataError("Réponse CoinGecko illisible.") from exc

def fetch_prices():
    ids = ",".join(item[0] for item in COINS.values())
    data = api_get("/simple/price", {"ids": ids, "vs_currencies": "eur", "include_24hr_change": "true"})
    result = {}
    for symbol, (coin_id, name) in COINS.items():
        item = data.get(coin_id, {})
        price = item.get("eur")
        if isinstance(price, bool) or not isinstance(price, (int, float)) or not np.isfinite(price) or price <= 0:
            continue
        result[symbol] = {"name": name, "price": float(price), "change_24h": item.get("eur_24h_change")}
    if not result:
        raise MarketDataError("Aucun cours exploitable reçu de CoinGecko.")
    return result

def fetch_history(symbol, days=90):
    if symbol not in COINS or days not in (90, 180):
        raise ValueError("Cryptomonnaie ou période invalide.")
    data = api_get(f"/coins/{COINS[symbol][0]}/market_chart", {"vs_currency": "eur", "days": days})
    points = data.get("prices", [])
    if len(points) < 40:
        raise MarketDataError("Historique insuffisant.")
    df = pd.DataFrame(points, columns=["timestamp", "price"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    daily = df.set_index("date")["price"].resample("1D").last().dropna()
    daily = daily[daily > 0]
    if len(daily) < 40:
        raise MarketDataError("Moins de 40 clôtures quotidiennes disponibles.")
    return daily

def indicators(prices):
    s = pd.Series(prices, dtype=float)
    delta = s.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = losses.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)
    rsi = rsi.mask((avg_loss == 0) & (avg_gain == 0), 50)
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return pd.DataFrame({"price": s, "sma10": s.rolling(10).mean(), "sma30": s.rolling(30).mean(), "rsi": rsi, "macd": macd, "macd_signal": signal}, index=s.index)

STRATEGIES = {"Tendance + MACD": "trend", "Croisement SMA + RSI": "cross"}

def signal_from_indicators(row, previous=None, strategy="trend"):
    if pd.isna(row["sma10"]) or pd.isna(row["sma30"]) or pd.isna(row["rsi"]):
        return "ATTENDRE", "Indicateurs insuffisants"
    if strategy == "cross":
        if previous is None or pd.isna(previous["sma10"]) or pd.isna(previous["sma30"]):
            return "ATTENDRE", "Croisement non vérifiable"
        if previous["sma10"] <= previous["sma30"] and row["sma10"] > row["sma30"] and row["rsi"] < 70:
            return "ACHETER", "Croisement haussier des moyennes mobiles"
        if previous["sma10"] >= previous["sma30"] and row["sma10"] < row["sma30"]:
            return "VENDRE", "Croisement baissier des moyennes mobiles"
        return "CONSERVER", "Aucun nouveau croisement"
    if row["sma10"] > row["sma30"] and row["macd"] > row["macd_signal"] and row["rsi"] < 70:
        return "ACHETER", "Tendance et MACD haussiers"
    if row["sma10"] < row["sma30"] or row["rsi"] > 75:
        return "VENDRE", "Tendance baissière ou RSI élevé"
    return "CONSERVER", "Signal non confirmé"

def portfolio_value(cash, positions, prices):
    return float(cash) + sum(float(qty) * prices[s]["price"] for s, qty in positions.items() if s in prices)

def backtest(prices, strategy="trend", fee=0.001, initial=10000.0):
    """Signal at day t close, simulated execution at day t+1 close (optimistic)."""
    df = indicators(prices).dropna(subset=["price"])
    if len(df) < 40:
        raise ValueError("Historique insuffisant pour le backtest.")
    cash, units = float(initial), 0.0
    equity, benchmark, trades = [], [], []
    start_price = float(df.iloc[0]["price"])
    for i in range(len(df)):
        row = df.iloc[i]
        price = float(row["price"])
        if i >= 1:
            prior = df.iloc[i-1]
            before = df.iloc[i-2] if i >= 2 else None
            action, _ = signal_from_indicators(prior, before, strategy)
            if action == "ACHETER" and units <= 1e-12 and cash > 0:
                spend = cash / (1 + fee)
                cost = spend * fee
                units = spend / price
                cash -= spend + cost
                trades.append({"Date": str(df.index[i].date()), "Action": "ACHAT", "Prix (€)": round(price, 6), "Frais (€)": round(cost, 3)})
            elif action == "VENDRE" and units > 1e-12:
                gross = units * price
                cost = gross * fee
                cash += gross - cost
                units = 0.0
                trades.append({"Date": str(df.index[i].date()), "Action": "VENTE", "Prix (€)": round(price, 6), "Frais (€)": round(cost, 3)})
        equity.append(cash + units * price)
        benchmark.append(initial * price / start_price)
    curve = pd.DataFrame({"Stratégie": equity, "Achat-conservation": benchmark}, index=df.index)
    drawdown = curve["Stratégie"] / curve["Stratégie"].cummax() - 1
    returns = curve["Stratégie"].pct_change().dropna()
    volatility = float(returns.std() * np.sqrt(365) * 100) if len(returns) > 1 else 0.0
    return {"curve": curve, "trades": trades, "return_pct": (equity[-1] / initial - 1) * 100, "benchmark_pct": (benchmark[-1] / initial - 1) * 100, "max_drawdown_pct": float(drawdown.min() * 100), "volatility_pct": volatility}
