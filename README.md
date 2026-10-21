# Crypto AI V7 — Crypto.com Exchange (simulation)

Tableau de bord Streamlit pédagogique utilisant **uniquement les endpoints publics** de Crypto.com Exchange.

- Marchés spot USDT détectés depuis `public/get-instruments` (pas de contrats dérivés).
- Cours via `public/get-tickers`, historique via `public/get-candlestick`.
- SMA, RSI, MACD, comparaison de deux stratégies et backtests simplifiés.
- Portefeuille, robot manuel et transactions **entièrement fictifs** en **USDT** (pas en EUR).
- Cache, messages d'erreur API, export CSV, sauvegarde JSON.
- **Aucun compte Crypto.com connecté. Aucun ordre réel. Aucune clé API.**

## Déploiement Streamlit

Créez un nouveau dépôt GitHub, par exemple `crypto-ai-v7`, et téléversez les quatre fichiers **à la racine**. Dans Streamlit Community Cloud, sélectionnez le dépôt, branche `main`, fichier principal `app.py`.

## Limitations

Les paires disponibles dépendent du catalogue Crypto.com Exchange et de son API. Les endpoints peuvent être indisponibles ou limités. Les frais de 0,1 % sont hypothétiques ; les backtests ne prennent pas en compte le spread, le slippage ou la fiscalité. Les signaux ne prédisent pas les cours. Le portefeuille fictif est stocké dans la session et peut être perdu : exportez le JSON.

Pour une future connexion privée, il faudra vérifier l'éligibilité du compte **Exchange** et les autorisations d'API. Ne jamais publier de clé ni de secret dans GitHub ; les ordres réels exigeraient une infrastructure séparée, des contrôles de risque, une validation et une autorisation explicite.

Documentation officielle : https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/crypto-com-exchange-api-v-1
