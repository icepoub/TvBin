"""
Configuration globale pour l'application TvBin.
"""
from typing import Dict, List, Union
import os
from pathlib import Path

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
BINANCE_API_KEY = ""  # À remplir avec votre clé API
BINANCE_API_SECRET = ""  # À remplir avec votre secret API
BINANCE_TLD = "com"  # com pour binance.com, us pour binance.us

# Configuration des paires de base
BASE_PAIRS = ["USDT", "USDC"]
DEFAULT_BASE_PAIR = "USDT"

# Configuration Discord
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1347182212839243816/8MiWiqEfyDBlQbvFhgmGN3ZmH1vGFqJhs8Gk_VRdWqL9bseatWbGRBoPYJTyCq-nNCVi"

# Ticker par défaut
DEFAULT_TICKER = "BTC"  # Bitcoin

# Liste des 200 premières cryptos (à remplacer par les vraies données de CoinMarketCap)
CRYPTO_TICKERS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "USDT", "USDC", "ADA", "AVAX", "DOGE",
    "DOT", "MATIC", "SHIB", "LTC", "UNI", "LINK", "XLM", "ATOM", "BCH", "CRO",
    "ALGO", "NEAR", "FIL", "VET", "ICP", "MANA", "SAND", "AXS", "HBAR", "XTZ",
    "EOS", "EGLD", "THETA", "AAVE", "ETC", "XMR", "CAKE", "GRT", "FTM", "FLOW",
    "KCS", "NEO", "KLAY", "QNT", "BSV", "MKR", "HNT", "CHZ", "ONE", "ENJ",
    "GALA", "WAVES", "ZEC", "DASH", "KSM", "BAT", "CELO", "AR", "ROSE", "COMP",
    "HOT", "STX", "NEXO", "LRC", "TFUEL", "KAVA", "RVN", "QTUM", "ZIL", "CRV",
    "YFI", "ANKR", "MINA", "IOTX", "ICX", "OMG", "STORJ", "SRM", "SNX", "IOTA",
    "1INCH", "GLM", "SUSHI", "XEM", "OCEAN", "AUDIO", "DYDX", "CELR", "ALPHA", "IOST",
    "BTTC", "HIVE", "REN", "SKL", "SXP", "SC", "ONT", "ZRX", "CTSI", "FET",
    "POLY", "STMX", "REEF", "COTI", "BNT", "SYS", "BAND", "RAY", "DENT", "RNDR",
    "PAXG", "DGB", "WAXP", "ARDR", "PERP", "POWR", "BAKE", "NKN", "OGN", "ALICE",
    "MBOX", "VTHO", "STEEM", "WRX", "PROM", "DUSK", "TWT", "STRAX", "RUNE", "RSR",
    "MTL", "ERG", "TOMO", "ANT", "BADGER", "FORTH", "LINA", "POND", "TRIBE", "SUPER",
    "MASK", "AGLD", "POLS", "HARD", "DODO", "VOXEL", "ALCX", "LOKA", "GHST", "WNXM",
    "ALPACA", "BOND", "FIDA", "FARM", "QUICK", "TOKE", "RARI", "YFII", "MOVR", "GLMR",
    "ASTR", "SCRT", "SPELL", "PEOPLE", "BICO", "JASMY", "API3", "DEXE", "IDEX", "RARE",
    "AUCTION", "KEEP", "TRAC", "MITH", "LOOM", "IRIS", "UNFI", "AKRO", "FRONT", "DEGO",
    "AERGO", "VITE", "NULS", "ORAI", "ARPA", "FIRO", "HXRO", "ORBS", "IOTX", "CTXC",
    "PIVX", "STPT", "AION", "DOCK", "PERL", "WING", "BURGER", "TROY", "COCOS", "DREP",
    "BTCST", "LINA", "DODO", "ALICE", "TLM", "FORTH", "PUNDIX", "MIR", "BAR", "MDX"
]

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