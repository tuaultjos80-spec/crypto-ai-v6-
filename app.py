"""Crypto AI V6 — simulation éducative uniquement, aucun ordre réel."""
import datetime as dt
import json
import math
import pandas as pd
import streamlit as st
from engine import COINS, STRATEGIES, MarketDataError, fetch_prices, fetch_history, indicators, signal_from_indicators, portfolio_value, backtest

st.set_page_config(page_title="Crypto AI V6", page_icon="📈", layout="wide")
st.title("📈 Crypto AI V6 — Trading virtuel")
st.warning("Argent fictif uniquement. Signaux déterministes, pas d'IA prédictive. Aucun ordre réel.")
st.caption("Cours CoinGecko indicatifs et parfois indisponibles. Backtests simplifiés : ils ne prédisent pas les performances futures.")
INITIAL = 10000.0
FEE = 0.001

@st.cache_data(ttl=300, show_spinner=False)
def get_prices():
    return fetch_prices()

@st.cache_data(ttl=3600, show_spinner=False)
def get_history(symbol, days):
    return fetch_history(symbol, days)

for key, default in {"cash": INITIAL, "positions": {s: 0.0 for s in COINS}, "trades": [], "last_cycle": [], "last_quotes": {}}.items():
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    st.header("⚙️ Paramètres")
    strategy_name = st.selectbox("Stratégie du robot", list(STRATEGIES))
    budget = st.number_input("Budget par achat fictif (€)", min_value=10.0, max_value=1000.0, value=100.0, step=10.0)
    max_allocation = st.slider("Allocation maximale par crypto (%)", 5, 30, 20, 5) / 100
    stop_loss = st.slider("Seuil indicatif de stop-loss (%)", 2, 20, 8, 1) / 100
    st.caption("Le stop-loss est vérifié uniquement lors d'un cycle manuel, pas en continu.")
    if st.button("🔄 Actualiser les données"):
        get_prices.clear()
        st.rerun()

try:
    quotes = get_prices()
    st.session_state.last_quotes = quotes
    quotes_fresh = True
except MarketDataError as exc:
    quotes = st.session_state.last_quotes
    quotes_fresh = False
    st.error(str(exc))
    if quotes:
        st.warning("Cours mémorisés dans cette session : ils peuvent être périmés. Transactions désactivées.")
    else:
        st.info("Aucun cours disponible. Attends quelques minutes puis actualise une seule fois.")

missing = [s for s in COINS if s not in quotes]
if missing:
    st.warning("Cours manquants : " + ", ".join(missing) + ". Les fonctions concernées sont désactivées.")

if not missing and quotes:
    value = portfolio_value(st.session_state.cash, st.session_state.positions, quotes)
    cols = st.columns(3)
    cols[0].metric("Portefeuille virtuel", f"{value:,.2f} €")
    cols[1].metric("Liquidités virtuelles", f"{st.session_state.cash:,.2f} €")
    cols[2].metric("Performance virtuelle", f"{(value / INITIAL - 1) * 100:+.2f} %")
else:
    st.metric("Liquidités virtuelles", f"{st.session_state.cash:,.2f} €")
    st.caption("Valorisation totale impossible sans tous les cours.")

st.subheader("🌍 Marché crypto")
if quotes:
    st.dataframe(pd.DataFrame([{"Crypto": s, "Nom": d["name"], "Prix (€)": d["price"], "Variation 24 h (%)": d["change_24h"]} for s, d in quotes.items()]), hide_index=True, use_container_width=True)

st.subheader("📉 Analyse technique")
symbol = st.selectbox("Crypto à analyser", list(COINS), key="analysis_symbol")
strategy = STRATEGIES[st.selectbox("Stratégie d'analyse", list(STRATEGIES), key="analysis_strategy")]
try:
    hist = get_history(symbol, 90)
    data = indicators(hist)
    current = data.iloc[-1]
    previous = data.iloc[-2]
    action, reason = signal_from_indicators(current, previous, strategy)
    st.line_chart(data[["price", "sma10", "sma30"]].rename(columns={"price": "Prix", "sma10": "SMA 10", "sma30": "SMA 30"}))
    st.write(f"**Signal théorique : {action}** — {reason}")
    st.write(f"RSI : {current['rsi']:.1f} | MACD : {current['macd']:.3f} | Signal MACD : {current['macd_signal']:.3f}")
except (MarketDataError, ValueError) as exc:
    st.info(f"Analyse indisponible : {exc}")

st.subheader("🧪 Backtesting et comparaison")
st.caption("Signal calculé sur la clôture précédente, exécution fictive à la clôture suivante. Hypothèses optimistes : pas de spread ni slippage, frais de 0,1 %.")
back_symbol = st.selectbox("Crypto du backtest", list(COINS), key="back_symbol")
days = st.selectbox("Période", [90, 180], format_func=lambda x: f"{x} jours")
if st.button("Lancer les deux backtests"):
    try:
        series = get_history(back_symbol, days)
        st.session_state.backtest_results = {name: backtest(series, code, fee=FEE) for name, code in STRATEGIES.items()}
        st.session_state.backtest_context = (back_symbol, days)
    except (MarketDataError, ValueError) as exc:
        st.error(f"Backtest indisponible : {exc}")
if "backtest_results" in st.session_state:
    sym_saved, days_saved = st.session_state.backtest_context
    st.write(f"**Résultats enregistrés : {sym_saved} — {days_saved} jours**")
    results = st.session_state.backtest_results
    summary = pd.DataFrame([{"Stratégie": name, "Performance (%)": round(result["return_pct"], 2), "Achat-conservation (%)": round(result["benchmark_pct"], 2), "Perte maximale (%)": round(result["max_drawdown_pct"], 2), "Volatilité annualisée (%)": round(result["volatility_pct"], 2), "Transactions": len(result["trades"])} for name, result in results.items()])
    st.dataframe(summary, hide_index=True, use_container_width=True)
    graph = pd.DataFrame({name: result["curve"]["Stratégie"] for name, result in results.items()})
    graph["Achat-conservation"] = next(iter(results.values()))["curve"]["Achat-conservation"]
    st.line_chart(graph)
    chosen = st.selectbox("Afficher les opérations fictives de", list(results))
    if results[chosen]["trades"]:
        st.dataframe(pd.DataFrame(results[chosen]["trades"]), hide_index=True, use_container_width=True)
    else:
        st.info("Aucune opération fictive pour cette stratégie et cette période.")
    st.caption("Attention : deux stratégies seulement, pas de validation hors échantillon. Le meilleur résultat historique n'est pas une garantie.")


def execute_trade(symbol, side, amount, source):
    if not quotes_fresh or symbol not in quotes:
        return "Cours indisponible ou périmé : opération désactivée."
    if not math.isfinite(amount) or amount <= 0:
        return "Montant invalide."
    price = quotes[symbol]["price"]
    fee = amount * FEE
    if side == "ACHAT":
        if amount + fee > st.session_state.cash + 1e-7:
            return "Liquidités insuffisantes."
        st.session_state.cash -= amount + fee
        st.session_state.positions[symbol] += amount / price
    else:
        units = amount / price
        if units > st.session_state.positions[symbol] + 1e-10:
            return "Position insuffisante."
        st.session_state.positions[symbol] = max(0.0, st.session_state.positions[symbol] - units)
        st.session_state.cash += amount - fee
    st.session_state.trades.append({"Date UTC": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "Crypto": symbol, "Action": side, "Montant (€)": round(amount, 2), "Prix (€)": price, "Frais (€)": round(fee, 4), "Source": source})
    return None

st.subheader("🤖 Robot virtuel — cycle manuel")
st.caption("Un clic = une analyse. Aucun ordre réel, aucun fonctionnement en arrière-plan. Un seul achat ou une seule vente fictive par crypto et par cycle.")
if st.button("Analyser et simuler un cycle", type="primary", disabled=not quotes_fresh or bool(missing)):
    notes = []
    for sym in COINS:
        try:
            series = get_history(sym, 90)
            frame = indicators(series)
            action, reason = signal_from_indicators(frame.iloc[-1], frame.iloc[-2], STRATEGIES[strategy_name])
            price = quotes[sym]["price"]
            holding = st.session_state.positions[sym] * price
            total = portfolio_value(st.session_state.cash, st.session_state.positions, quotes)
            # Indicative risk proxy: recent 30-day high, NOT an actual entry-based stop-loss.
            recent_high = float(series.tail(30).max())
            if holding >= 0.01 and price <= recent_high * (1 - stop_loss):
                action = "VENDRE"
                reason = "Seuil de repli depuis le plus haut sur 30 jours"
            if action == "ACHETER" and holding < 0.01:
                amount = min(budget, max(0.0, total * max_allocation - holding), st.session_state.cash / (1 + FEE))
                if amount >= 10:
                    error = execute_trade(sym, "ACHAT", amount, "Robot virtuel")
                    notes.append(f"{sym} : achat fictif {amount:.2f} €" if error is None else f"{sym} : {error}")
                else:
                    notes.append(f"{sym} : budget insuffisant")
            elif action == "VENDRE" and holding >= 0.01:
                error = execute_trade(sym, "VENTE", holding, "Robot virtuel")
                notes.append(f"{sym} : vente fictive {holding:.2f} € ({reason})" if error is None else f"{sym} : {error}")
            else:
                notes.append(f"{sym} : {action.lower()} — aucun ordre")
        except (MarketDataError, ValueError) as exc:
            notes.append(f"{sym} : données indisponibles ({exc})")
    st.session_state.last_cycle = notes
    st.rerun()
for note in st.session_state.last_cycle:
    st.write("• " + note)

st.subheader("💶 Transaction manuelle fictive")
with st.form("manual_order"):
    sym = st.selectbox("Cryptomonnaie", list(COINS), key="manual_symbol")
    side = st.radio("Opération", ["ACHAT", "VENTE"], horizontal=True)
    amount = st.number_input("Montant (€)", min_value=1.0, value=100.0, step=10.0)
    submitted = st.form_submit_button("Valider l'ordre virtuel", disabled=not quotes_fresh or sym not in quotes)
if submitted:
    error = execute_trade(sym, side, amount, "Manuel")
    if error:
        st.error(error)
    else:
        st.success("Transaction fictive enregistrée.")
        st.rerun()

st.subheader("📊 Positions et risques")
rows = []
for sym, qty in st.session_state.positions.items():
    val = qty * quotes[sym]["price"] if sym in quotes else None
    rows.append({"Crypto": sym, "Unités": qty, "Valeur indicative (€)": val})
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
st.caption("Les prix peuvent être différés. Le seuil de risque n'est pas un stop-loss garanti : il n'est évalué qu'au clic et utilise un sommet historique de 30 jours.")

st.subheader("📜 Historique des opérations")
if st.session_state.trades:
    table = pd.DataFrame(st.session_state.trades)
    st.dataframe(table.iloc[::-1], hide_index=True, use_container_width=True)
    st.download_button("Télécharger le CSV", table.to_csv(index=False).encode("utf-8-sig"), "crypto-ai-v6-trades.csv", "text/csv")
else:
    st.info("Aucune transaction fictive.")

st.subheader("💾 Sauvegarde et restauration")
backup = {"version": 6, "cash": st.session_state.cash, "positions": st.session_state.positions, "trades": st.session_state.trades}
st.download_button("Télécharger la sauvegarde JSON", json.dumps(backup, ensure_ascii=False, indent=2), "crypto-ai-v6-backup.json", "application/json")
upload = st.file_uploader("Importer une sauvegarde JSON", type=["json"])
if upload is not None and st.button("Restaurer la sauvegarde"):
    try:
        if upload.size > 2_000_000:
            raise ValueError("Fichier trop volumineux")
        restored = json.load(upload)
        cash = float(restored["cash"])
        positions = restored["positions"]
        trades = restored["trades"]
        if not math.isfinite(cash) or not 0 <= cash <= 1e12:
            raise ValueError("Liquidités invalides")
        if not isinstance(positions, dict) or set(positions) != set(COINS) or not isinstance(trades, list) or len(trades) > 10000:
            raise ValueError("Format de sauvegarde invalide")
        positions = {s: float(positions[s]) for s in COINS}
        if any(not math.isfinite(q) or not 0 <= q <= 1e12 for q in positions.values()):
            raise ValueError("Positions invalides")
        st.session_state.cash = cash
        st.session_state.positions = positions
        st.session_state.trades = trades
        st.session_state.last_cycle = []
        st.rerun()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        st.error(f"Sauvegarde invalide : {exc}")
if st.button("Réinitialiser le portefeuille fictif"):
    st.session_state.cash = INITIAL
    st.session_state.positions = {s: 0.0 for s in COINS}
    st.session_state.trades = []
    st.session_state.last_cycle = []
    st.rerun()
st.caption("La session Streamlit peut être effacée. Frais simulés 0,1 %, sans spread, slippage ni fiscalité. Aucun conseil financier.")
