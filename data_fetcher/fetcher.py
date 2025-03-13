"""
Module pour récupérer les données de cryptomonnaies via l'API Binance.
"""
from typing import Dict, List, Optional, Union, Tuple
import os
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException
import pytz
import time
from pathlib import Path

import config

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_CONFIG["format"],
    filename=config.LOG_CONFIG["file"]
)
logger = logging.getLogger(__name__)

class DataFetcher:
    """
    Classe pour récupérer les données de cryptomonnaies via l'API Binance.
    """
    
    def __init__(self, cache_dir: Path = config.TICKERS_DIR):
        """
        Initialise le récupérateur de données.
        
        Args:
            cache_dir: Répertoire pour le cache des données
        """
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialiser le client Binance
        self.client = Client(
            config.BINANCE_API_KEY,
            config.BINANCE_API_SECRET,
            tld=config.BINANCE_TLD
        )
        
        # Timeframes Binance
        self.timeframe_map = {
            "12h": Client.KLINE_INTERVAL_12HOUR,
            "1d": Client.KLINE_INTERVAL_1DAY,
            "1w": Client.KLINE_INTERVAL_1WEEK
        }
        
        # Fuseaux horaires
        self.utc_tz = pytz.timezone('UTC')
        
        logger.info(f"DataFetcher initialisé avec cache dans {self.cache_dir}")
    
    def _get_cache_path(self, symbol: str, timeframe: str) -> Path:
        """
        Obtient le chemin du fichier de cache pour un symbole et un timeframe.
        
        Args:
            symbol: Symbole de la cryptomonnaie
            timeframe: Intervalle de temps
            
        Returns:
            Chemin du fichier de cache
        """
        filename = f"{symbol}_{timeframe}.csv"
        return self.cache_dir / filename
    
    def _should_update_data(self, last_update: datetime) -> bool:
        """
        Détermine si les données doivent être mises à jour.
        
        Args:
            last_update: Date de la dernière mise à jour
            
        Returns:
            True si les données doivent être mises à jour, False sinon
        """
        now = datetime.now(self.utc_tz)
        
        # Mettre à jour si la dernière mise à jour date de plus de 12h
        if (now - last_update) > timedelta(hours=12):
            return True
            
        return False
    
    def _format_binance_data(self, klines: List) -> pd.DataFrame:
        """
        Formate les données Binance en DataFrame pandas.
        
        Args:
            klines: Données Binance
            
        Returns:
            DataFrame avec les données formatées
        """
        columns = [
            'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
            'Close time', 'Quote asset volume', 'Number of trades',
            'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
        ]
        
        df = pd.DataFrame(klines, columns=columns)
        
        # Convertir les colonnes numériques
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col])
        
        # Convertir les timestamps en datetime
        df['Open time'] = pd.to_datetime(df['Open time'], unit='ms')
        df['Close time'] = pd.to_datetime(df['Close time'], unit='ms')
        
        # Utiliser Open time comme index
        df.set_index('Open time', inplace=True)
        
        return df
    
    def get_ticker_data(
        self, 
        symbol: str, 
        timeframe: str = "1d", 
        months: int = 6, 
        use_cache: bool = True, 
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Récupère les données d'un ticker.
        
        Args:
            symbol: Symbole de la cryptomonnaie (sans /USDT ou /USDC)
            timeframe: Intervalle de temps
            months: Nombre de mois d'historique
            use_cache: Utiliser le cache
            force_refresh: Forcer le rafraîchissement des données
            
        Returns:
            DataFrame avec les données OHLCV
        """
        # Vérifier que le timeframe est valide
        if timeframe not in self.timeframe_map:
            logger.error(f"Timeframe {timeframe} non supporté")
            return pd.DataFrame()
        
        # Essayer d'abord avec USDT
        usdt_symbol = f"{symbol}USDT"
        usdt_cache_file = self._get_cache_path(usdt_symbol, timeframe)
        
        # Vérifier le cache pour USDT
        if use_cache and not force_refresh and os.path.exists(usdt_cache_file):
            try:
                df = pd.read_csv(usdt_cache_file, index_col=0, parse_dates=True)
                last_date = pd.to_datetime(df.index[-1])
                
                if not self._should_update_data(last_date):
                    logger.info(f"Utilisation des données en cache pour {usdt_symbol} ({timeframe})")
                    return df
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du cache pour {usdt_symbol}: {e}")
        
        # Calculer les dates de début et de fin
        end_date = int(time.time() * 1000)  # Timestamp en millisecondes
        start_date = end_date - (months * 30 * 24 * 60 * 60 * 1000)  # months mois en arrière
        
        # Essayer de récupérer les données avec USDT
        try:
            logger.info(f"Récupération des données pour {usdt_symbol} ({timeframe})")
            klines = self.client.get_historical_klines(
                usdt_symbol,
                self.timeframe_map[timeframe],
                start_str=start_date,
                end_str=end_date
            )
            
            if klines:
                df = self._format_binance_data(klines)
                
                if use_cache:
                    df.to_csv(usdt_cache_file)
                    logger.info(f"Données sauvegardées dans {usdt_cache_file}")
                
                return df
        except BinanceAPIException as e:
            logger.warning(f"Erreur API Binance pour {usdt_symbol}: {e}")
        
        # Si USDT a échoué, essayer avec USDC
        usdc_symbol = f"{symbol}USDC"
        usdc_cache_file = self._get_cache_path(usdc_symbol, timeframe)
        
        # Vérifier le cache pour USDC
        if use_cache and not force_refresh and os.path.exists(usdc_cache_file):
            try:
                df = pd.read_csv(usdc_cache_file, index_col=0, parse_dates=True)
                last_date = pd.to_datetime(df.index[-1])
                
                if not self._should_update_data(last_date):
                    logger.info(f"Utilisation des données en cache pour {usdc_symbol} ({timeframe})")
                    return df
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du cache pour {usdc_symbol}: {e}")
        
        # Essayer de récupérer les données avec USDC
        try:
            logger.info(f"Récupération des données pour {usdc_symbol} ({timeframe})")
            klines = self.client.get_historical_klines(
                usdc_symbol,
                self.timeframe_map[timeframe],
                start_str=start_date,
                end_str=end_date
            )
            
            if klines:
                df = self._format_binance_data(klines)
                
                if use_cache:
                    df.to_csv(usdc_cache_file)
                    logger.info(f"Données sauvegardées dans {usdc_cache_file}")
                
                return df
        except BinanceAPIException as e:
            logger.warning(f"Erreur API Binance pour {usdc_symbol}: {e}")
            
            # Envoyer une alerte via Discord
            from discord_notifier.notifier import DiscordNotifier
            notifier = DiscordNotifier()
            notifier.send_ticker_not_found_alert(symbol)
        
        # Si tout a échoué, retourner un DataFrame vide
        logger.error(f"Impossible de récupérer les données pour {symbol} (ni en USDT, ni en USDC)")
        return pd.DataFrame()
    
    def get_all_symbols(self) -> List[str]:
        """
        Récupère la liste de tous les symboles disponibles sur Binance.
        
        Returns:
            Liste des symboles
        """
        try:
            exchange_info = self.client.get_exchange_info()
            
            # Filtrer les symboles qui se terminent par USDT ou USDC
            symbols = []
            for symbol_info in exchange_info['symbols']:
                symbol = symbol_info['symbol']
                if symbol.endswith('USDT'):
                    base_symbol = symbol[:-4]  # Enlever USDT
                    if base_symbol not in symbols:
                        symbols.append(base_symbol)
                elif symbol.endswith('USDC'):
                    base_symbol = symbol[:-4]  # Enlever USDC
                    if base_symbol not in symbols:
                        symbols.append(base_symbol)
            
            return symbols
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des symboles: {e}")
            return []