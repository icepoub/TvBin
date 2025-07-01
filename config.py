"""
Configuration globale pour l'application TvBin.
"""
from typing import Dict, List, Union
import os
from pathlib import Path
import json

# Chemins de base
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TICKERS_DIR = BASE_DIR / "data" / "tickers"

# Créer les répertoires s'ils n'existent pas
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TICKERS_DIR, exist_ok=True)

# Configuration de l'application
APP_CONFIG = {
    "host": "127.0.0.1",
    "port": 8070,
    "debug": True,
    "title": "TvBin - ZLMA Trend Levels pour Crypto",
    "theme": "darkly"
}

# Configuration des indicateurs
INDICATOR_CONFIG = {
    "ema_period": 15,
    "zlma_period": 15,
    "timeframes": ["12h", "1d", "1w"],
    "default_timeframe": "1d",
    "history_months": 6
}

# Configuration Binance
BINANCE_API_KEY = "iYYM8Zrx1BZiR721a9P9etq7CP1V5E0uNWr3uqhbadUVgivVVmFLA3kDUOFMc8Xy"  # Clé API Binance testnet
BINANCE_API_SECRET = "VLoOAPmBSTRChBnf4UrCSnzPg9sHwhaKMlTllGJHd8hXeJBjX0KIfPTwO1uPjYpr"  # Secret API Binance testnet
BINANCE_TLD = "com"  # com pour binance.com, us pour binance.us

# Configuration des paires de base
BASE_PAIRS = ["USDT", "USDC"]
DEFAULT_BASE_PAIR = "USDT"

# Configuration Discord
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1349759237663883314/xd34KYdFL5jfTEfGr7Bu4gkaPUjWHns-ewIDWtZdK6FdehPhRJ4mGpz2N3H9MF7kfqNy"

# Ticker par défaut
DEFAULT_TICKER = "BTC"  # Bitcoin

# Charger dynamiquement la liste des tickers depuis le fichier JSON
CRYPTO_TICKERS_PATH = DATA_DIR / "crypto_tickers.json"
if CRYPTO_TICKERS_PATH.exists():
    with open(CRYPTO_TICKERS_PATH, "r") as f:
        CRYPTO_TICKERS = json.load(f)
else:
    CRYPTO_TICKERS = []

# Configuration du backtesting
BACKTEST_CONFIG = {
    "initial_capital": 10000,
    "position_size_pct": 0.1,  # 10% du capital par position
    "stop_loss_pct": 0.05,     # 5% de stop loss
    "take_profit_pct": 0.1     # 10% de take profit
}

# Configuration de la sauvegarde
SAVE_CONFIG = {
    "signals_file": "signals.csv",
    "backtest_file": "backtest_results.csv",
    "ticker_data_format": "{ticker}_{timeframe}.csv"
}

# Paramètres de logging
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "tvbin.log"
}

# Configuration de la mise à jour des données
UPDATE_CONFIG = {
    "min_update_interval_hours": 12,  # Intervalle minimum entre les mises à jour
    "max_requests_per_minute": 30     # Limite de requêtes API par minute
}

# Configuration CoinMarketCap
COINMARKETCAP_API_KEY = "9e0ee532-5e56-421b-97b3-b91a4e68bd2e"