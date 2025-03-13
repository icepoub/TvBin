# TvBin

TvBin est une application de trading automatique pour les cryptomonnaies, basée sur AutoTV Yolo. Elle utilise l'API Binance pour récupérer les données des 200 premières cryptomonnaies de CoinMarketCap.

## Fonctionnalités

- Récupération des données via l'API Binance
- Support des paires de trading (X/USDT avec fallback sur X/USDC)
- Calcul d'indicateurs techniques (EMA, ZLMA)
- Détection de signaux de trading
- Interface utilisateur web avec Dash
- Notifications Discord
- Backtesting des stratégies

## Différences avec AutoTV Yolo

- Adapté pour les cryptomonnaies au lieu des actions
- Utilise l'API Binance au lieu de Yahoo Finance
- Supporte les timeframes 12h, 1d, 1w
- Optimisé pour limiter les requêtes API (mise à jour toutes les 12h)
- Système de fallback pour les paires de trading (USDT → USDC)
- Alertes Discord pour les tickers non trouvés

## Installation

```bash
# Cloner le dépôt
git clone https://github.com/oferce/TvBin.git
cd TvBin

# Installer les dépendances
pip install -r requirements.txt

# Configurer les clés API Binance dans config.py

# Lancer l'application
python run_on_8070.py
```

## Configuration

Modifiez le fichier `config.py` pour configurer :
- Les clés API Binance
- Les timeframes à utiliser
- La fréquence de mise à jour des données
- Le webhook Discord pour les notifications

## Licence

Ce projet est sous licence MIT.