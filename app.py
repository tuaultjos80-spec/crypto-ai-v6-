import json
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from engine import ASSETS, FEE, MarketError, spot_pairs, tickers, history, indicators, decision, backtest

st.set_page_config(page_title='Crypto AI V7', page_icon='🪙', layout='wide')
st.title('🪙 Crypto AI V7 — Crypto.com Exchange')
st.warning('MODE SIMULATION UNIQUEMENT. Aucun accès au compte Crypto.com, aucune clé API et aucun ordre réel.')
st.caption('Prix et portefeuille en USDT, PAS en euros. Les cours Exchange peuvent différer de ceux de l’application Crypto.com.')

@st.cache_data(ttl=3600, show_spinner=False)
def pairs_cached():
    return spot_pairs()

@st.cache_data(ttl=90, show_spinner=False)
def tickers_cached(pairs_tuple):
    return tickers(dict(pairs_tuple))

@st.cache_data(ttl=1800, show_spinner=False)
def history_cached(pair, days):
    return history(pair, days)

if 'paper' not in st.session_state:
    st.session_state.paper = {'cash': 10000.0, 'positions': {a: 0.0 for a in ASSETS}, 'trades': []}

with st.sidebar:
    st.header('⚙️ Paramètres')
    strategy = st.selectbox('Stratégie du robot', ['Tendance + MACD', 'Croisement SMA + RSI'])
    max_allocation = st.slider('Allocation maximale par crypto (%)', 1, 20, 10)
    trade_budget = st.number_input('Montant fictif par achat (USDT)', 10.0, 1000.0, 100.0, step=10.0)
    st.caption('Le robot s’active uniquement par clic. Pas de stop-loss automatique ni de fonctionnement 24 h/24.')

try:
    pairs = pairs_cached()
    if not pairs:
        st.error('Aucune paire spot USDT trouvée dans le catalogue Crypto.com Exchange. Réessayez plus tard.')
        st.stop()
    quotes = tickers_cached(tuple(sorted(pairs.items())))
except MarketError as exc:
    st.error(str(exc))
    st.info('Attendez quelques minutes avant de rafraîchir. Aucun ordre fictif ne sera exécuté sans prix valide.')
    st.stop()

if not quotes:
    st.error('Aucune cotation disponible. Réessayez ultérieurement.')
    st.stop()

paper = st.session_state.paper
portfolio = paper['cash'] + sum(paper['positions'].get(a, 0) * q['price'] for a, q in quotes.items())
col1, col2, col3 = st.columns(3)
col1.metric('Portefeuille fictif (USDT)', f'{portfolio:,.2f}')
col2.metric('Liquidités fictives (USDT)', f"{paper['cash']:,.2f}")
col3.metric('Performance fictive', f'{(portfolio/10000-1)*100:+.2f} %')

st.subheader('🌐 Marché Crypto.com Exchange')
market = [{'Crypto': a, 'Paire spot': q['pair'], 'Prix (USDT)': q['price'], 'Variation 24 h (%)': round(q['change'], 2),
           'Horodatage UTC': str(q['timestamp']) if q['timestamp'] is not None else 'Non fourni'} for a, q in quotes.items()]
st.dataframe(pd.DataFrame(market), use_container_width=True, hide_index=True)
st.caption('Les données sont mises en cache 90 secondes. Variation 24 h indicative selon la donnée retournée par Crypto.com.')

st.subheader('📉 Analyse technique')
asset = st.selectbox('Crypto à analyser', list(quotes))
days = st.selectbox('Historique demandé', [90, 180], index=0)
try:
    series = history_cached(quotes[asset]['pair'], days)
    ind = indicators(series)
    st.line_chart(ind[['Cours', 'SMA10', 'SMA30']])
    st.write(f"Signal de **{asset}** avec **{strategy}** : **{decision(ind.iloc[-1], strategy)}**")
    st.caption(f'{len(series)} bougies disponibles. Une bougie journalière peut être encore en formation.')
except MarketError as exc:
    st.warning(f'Analyse indisponible : {exc}')
    series = None

st.subheader('🧪 Backtests simplifiés')
st.caption('Signaux calculés à la clôture précédente, exécution à la clôture suivante. Frais hypothétiques de 0,1 % par ordre ; hors spread, slippage et fiscalité.')
if series is not None and st.button('Comparer les deux stratégies'):
    results = []
    chart = pd.DataFrame()
    for strat in ['Tendance + MACD', 'Croisement SMA + RSI']:
        values, hold, perf, dd, orders = backtest(series, strat, days)
        results.append({'Stratégie': strat, 'Performance (%)': round(perf, 2), 'Drawdown max (%)': round(dd, 2), 'Ordres fictifs': len(orders)})
        chart[strat] = values
        chart['Achat-conservation'] = hold
    st.session_state.backtest_result = {'table': results, 'chart': chart}
if 'backtest_result' in st.session_state:
    st.dataframe(pd.DataFrame(st.session_state.backtest_result['table']), use_container_width=True, hide_index=True)
    st.line_chart(st.session_state.backtest_result['chart'])

st.subheader('🤖 Robot fictif — cycle manuel')
if st.button('Analyser et simuler un cycle', type='primary'):
    outcomes = []
    for a, quote in quotes.items():
        try:
            h = history_cached(quote['pair'], 90)
            sig = decision(indicators(h).iloc[-1], strategy)
            price = quote['price']
            units = paper['positions'].get(a, 0)
            total = paper['cash'] + sum(paper['positions'].get(x, 0) * quotes[x]['price'] for x in quotes)
            if sig == 'ACHETER' and units == 0:
                budget = min(trade_budget, paper['cash'], max(0.0, total * max_allocation / 100))
                if budget >= 10:
                    paper['cash'] -= budget
                    paper['positions'][a] = budget * (1 - FEE) / price
                    paper['trades'].append({'Date UTC': datetime.now(timezone.utc).isoformat(), 'Crypto': a, 'Action': 'ACHAT', 'Montant USDT': round(budget, 2)})
                    outcomes.append(f'{a} : ACHAT fictif {budget:.2f} USDT')
                else:
                    outcomes.append(f'{a} : ACHETER — liquidités ou limite insuffisantes')
            elif sig == 'VENDRE' and units > 0:
                received = units * price * (1 - FEE)
                paper['cash'] += received
                paper['positions'][a] = 0.0
                paper['trades'].append({'Date UTC': datetime.now(timezone.utc).isoformat(), 'Crypto': a, 'Action': 'VENTE', 'Montant USDT': round(received, 2)})
                outcomes.append(f'{a} : VENTE fictive {received:.2f} USDT')
            else:
                outcomes.append(f'{a} : {sig} — aucun ordre')
        except (MarketError, ValueError) as exc:
            outcomes.append(f'{a} : données indisponibles — {exc}')
    st.session_state.last_cycle = outcomes
if 'last_cycle' in st.session_state:
    for line in st.session_state.last_cycle:
        st.write('• ' + line)

st.subheader('💵 Opération manuelle fictive')
with st.form('paper_trade'):
    symbol = st.selectbox('Cryptomonnaie', list(quotes), key='manual_symbol')
    action = st.radio('Opération', ['ACHAT', 'VENTE'], horizontal=True)
    amount = st.number_input('Montant en USDT', min_value=10.0, max_value=1000.0, value=100.0)
    submitted = st.form_submit_button('Valider l’ordre virtuel')
if submitted:
    price = quotes[symbol]['price']
    current = paper['positions'].get(symbol, 0)
    total = paper['cash'] + sum(paper['positions'].get(x, 0) * quotes[x]['price'] for x in quotes)
    if action == 'ACHAT':
        if amount > paper['cash']:
            st.error('Liquidités fictives insuffisantes.')
        elif (current * price + amount) > total * max_allocation / 100:
            st.error('Limite d’allocation dépassée.')
        else:
            paper['cash'] -= amount
            paper['positions'][symbol] = current + amount * (1-FEE) / price
            paper['trades'].append({'Date UTC': datetime.now(timezone.utc).isoformat(), 'Crypto': symbol, 'Action': action, 'Montant USDT': amount})
            st.success('Achat fictif enregistré.')
    elif amount > current * price:
        st.error('Position fictive insuffisante pour vendre ce montant.')
    else:
        paper['positions'][symbol] = max(0, current - amount / price)
        paper['cash'] += amount * (1-FEE)
        paper['trades'].append({'Date UTC': datetime.now(timezone.utc).isoformat(), 'Crypto': symbol, 'Action': action, 'Montant USDT': amount})
        st.success('Vente fictive enregistrée.')

st.subheader('📊 Positions fictives')
st.dataframe(pd.DataFrame([{'Crypto': a, 'Unités': paper['positions'].get(a, 0), 'Valeur USDT': paper['positions'].get(a, 0) * quotes[a]['price']} for a in quotes]), hide_index=True, use_container_width=True)
st.subheader('📜 Historique des opérations')
if paper['trades']:
    trades = pd.DataFrame(paper['trades'])
    st.dataframe(trades, use_container_width=True, hide_index=True)
    st.download_button('Télécharger le CSV', trades.to_csv(index=False).encode('utf-8'), 'operations_v7.csv', 'text/csv')
else:
    st.info('Aucune opération fictive enregistrée.')

st.subheader('💾 Sauvegarde / restauration')
st.download_button('Télécharger la sauvegarde JSON', json.dumps(paper, indent=2).encode('utf-8'), 'crypto_ai_v7_backup.json', 'application/json')
backup = st.file_uploader('Importer une sauvegarde V7', type=['json'])
if backup is not None and st.button('Restaurer la sauvegarde'):
    try:
        data = json.load(backup)
        if not isinstance(data, dict) or not isinstance(data.get('positions'), dict) or not isinstance(data.get('trades'), list):
            raise ValueError('Structure invalide')
        cash = float(data['cash'])
        positions = {a: float(data['positions'].get(a, 0)) for a in ASSETS}
        if not (0 <= cash <= 1e9) or any(not (0 <= q <= 1e9) for q in positions.values()) or len(data['trades']) > 10000:
            raise ValueError('Valeurs hors limites')
        st.session_state.paper = {'cash': cash, 'positions': positions, 'trades': data['trades']}
        st.success('Sauvegarde restaurée. Actualisez la page si nécessaire.')
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        st.error(f'Sauvegarde refusée : {exc}')
st.caption('Session Streamlit : l’état fictif peut être perdu après redémarrage. Exportez régulièrement votre sauvegarde JSON. Aucune clé API requise ni prise en charge dans cette version.')
