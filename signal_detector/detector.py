"""
Module pour détecter et gérer les signaux de trading.
"""
from typing import Dict, List, Optional, Union, Tuple
import logging
import os
import pandas as pd
from datetime import datetime
from pathlib import Path
import numpy as np

import config
from data_fetcher.fetcher import DataFetcher
from indicator_calculator.indicators import IndicatorCalculator

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_CONFIG["format"],
    filename=config.LOG_CONFIG["file"]
)
logger = logging.getLogger(__name__)

class SignalDetector:
    """
    Classe pour détecter et gérer les signaux de trading.
    """
    
    def __init__(
        self, 
        data_fetcher: Optional[DataFetcher] = None,
        indicator_calculator: Optional[IndicatorCalculator] = None,
        save_dir: Path = config.DATA_DIR
    ):
        """
        Initialise le détecteur de signaux.
        
        Args:
            data_fetcher: Instance de DataFetcher
            indicator_calculator: Instance de IndicatorCalculator
            save_dir: Répertoire pour sauvegarder les signaux
        """
        self.data_fetcher = data_fetcher or DataFetcher()
        self.indicator_calculator = indicator_calculator or IndicatorCalculator(
            ema_period=config.INDICATOR_CONFIG["ema_period"],
            zlma_period=config.INDICATOR_CONFIG["zlma_period"]
        )
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        self.signals_file = self.save_dir / config.SAVE_CONFIG["signals_file"]
        
        # Charger les signaux existants
        self.signals_history = self._load_signals_history()
        
        logger.info(f"SignalDetector initialisé avec sauvegarde dans {self.save_dir}")
    
    def detect_signals(
        self, 
        symbol: str, 
        timeframe: str = "1d", 
        months: int = 6,
        save_signals: bool = True,
        force_refresh: bool = False
    ) -> Dict:
        """
        Détecte les signaux pour un symbole.
        
        Args:
            symbol: Symbole de la cryptomonnaie
            timeframe: Intervalle de temps
            months: Nombre de mois d'historique
            save_signals: Sauvegarder les signaux détectés
            force_refresh: Forcer le rafraîchissement des données
            
        Returns:
            Dictionnaire contenant les informations sur les signaux
        """
        # Récupérer les données
        data = self.data_fetcher.get_ticker_data(symbol, timeframe, months, force_refresh=force_refresh)
        
        if data.empty:
            logger.warning(f"Aucune donnée disponible pour {symbol}, impossible de détecter des signaux")
            return {"symbol": symbol, "signals": [], "last_signal": None}
        
        # Calculer les indicateurs et détecter les signaux
        data_with_indicators = self.indicator_calculator.add_indicators(data)
        
        # Récupérer tous les signaux
        all_signals = self.indicator_calculator.get_all_signals(data_with_indicators)
        
        # Récupérer le dernier signal
        last_signal = self.indicator_calculator.get_last_signal(data_with_indicators)
        
        # Préparer le résultat
        result = {
            "symbol": symbol,
            "timeframe": timeframe,
            "last_update": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "signals_count": len(all_signals),
            "bullish_signals": len(all_signals[all_signals['Signal'] == 1]) if not all_signals.empty else 0,
            "bearish_signals": len(all_signals[all_signals['Signal'] == -1]) if not all_signals.empty else 0,
            "last_signal": last_signal,
            "last_price": data['Close'].iloc[-1] if not data.empty else None,
            "all_signals": all_signals.to_dict('records') if not all_signals.empty else []
        }
        
        # Sauvegarder les signaux
        if save_signals:
            self._save_signal(symbol, timeframe, last_signal, data['Close'].iloc[-1])
        
        return result
    
    def detect_signals_for_multiple(
        self, 
        symbols: List[str], 
        timeframe: str = "1d", 
        months: int = 6
    ) -> Dict[str, Dict]:
        """
        Détecte les signaux pour plusieurs symboles.
        
        Args:
            symbols: Liste des symboles de cryptomonnaies
            timeframe: Intervalle de temps
            months: Nombre de mois d'historique
            
        Returns:
            Dictionnaire {symbol: résultat}
        """
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.detect_signals(symbol, timeframe, months)
            except Exception as e:
                logger.error(f"Erreur lors de la détection des signaux pour {symbol}: {e}")
                results[symbol] = {"symbol": symbol, "error": str(e)}
        
        return results
    
    def get_active_signals(self, timeframe: str = "1d") -> pd.DataFrame:
        """
        Récupère les signaux actifs (dernières 24h pour daily, dernière semaine pour weekly).
        
        Args:
            timeframe: Intervalle de temps
            
        Returns:
            DataFrame contenant les signaux actifs
        """
        if self.signals_history.empty:
            return pd.DataFrame()
        
        # Filtrer par timeframe
        signals = self.signals_history[self.signals_history['timeframe'] == timeframe].copy()
        
        if signals.empty:
            return pd.DataFrame()
        
        # Convertir la date en datetime
        signals['date'] = pd.to_datetime(signals['date'])
        
        # Filtrer par date
        now = datetime.now()
        if timeframe == "1d":
            # Signaux des dernières 24h
            active_signals = signals[signals['date'] >= pd.Timestamp(now.date())]
        elif timeframe == "1w":
            # Signaux de la dernière semaine
            active_signals = signals[signals['date'] >= pd.Timestamp(now.date()).floor('D') - pd.Timedelta(days=7)]
        else:
            active_signals = signals
        
        return active_signals
    
    def _save_signal(
        self, 
        symbol: str, 
        timeframe: str, 
        signal_info: Dict, 
        current_price: float
    ) -> None:
        """
        Sauvegarde un signal dans l'historique.
        
        Args:
            symbol: Symbole de la cryptomonnaie
            timeframe: Intervalle de temps
            signal_info: Informations sur le signal
            current_price: Prix actuel
        """
        # Vérifier que signal_info contient les clés nécessaires
        if not signal_info or 'signal' not in signal_info:
            logger.warning(f"Informations de signal invalides pour {symbol}")
            return
            
        # Convertir en type primitif pour éviter l'ambiguïté
        signal_value = int(signal_info['signal']) if isinstance(signal_info['signal'], (pd.Series, np.ndarray)) else signal_info['signal']
        
        if signal_value == 0:
            return  # Ne pas sauvegarder les non-signaux
        
        # Créer une nouvelle entrée
        new_signal = {
            'symbol': symbol,
            'timeframe': timeframe,
            'date': signal_info['date'],
            'signal': signal_value,
            'price': float(signal_info['price']) if isinstance(signal_info['price'], (pd.Series, np.ndarray)) else signal_info['price'],
            'current_price': float(current_price) if isinstance(current_price, (pd.Series, np.ndarray)) else current_price,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Vérifier si ce signal existe déjà
        if not self.signals_history.empty:
            existing = self.signals_history[
                (self.signals_history['symbol'] == symbol) & 
                (self.signals_history['timeframe'] == timeframe) & 
                (self.signals_history['date'] == signal_info['date']) &
                (self.signals_history['signal'] == signal_value)
            ]
            
            if not existing.empty:
                logger.info(f"Signal déjà enregistré pour {symbol} ({timeframe}) le {signal_info['date']}")
                return
        
        # Ajouter le nouveau signal
        self.signals_history = pd.concat([
            self.signals_history, 
            pd.DataFrame([new_signal])
        ], ignore_index=True)
        
        # Sauvegarder l'historique mis à jour
        self._save_signals_history()
        
        logger.info(f"Signal {'haussier' if signal_value == 1 else 'baissier'} "
                   f"sauvegardé pour {symbol} ({timeframe}) le {signal_info['date']}")
    
    def _load_signals_history(self) -> pd.DataFrame:
        """
        Charge l'historique des signaux depuis le fichier.
        
        Returns:
            DataFrame contenant l'historique des signaux
        """
        if os.path.exists(self.signals_file):
            try:
                return pd.read_csv(self.signals_file)
            except Exception as e:
                logger.error(f"Erreur lors du chargement de l'historique des signaux: {e}")
        
        # Créer un DataFrame vide avec les colonnes appropriées
        return pd.DataFrame(columns=[
            'symbol', 'timeframe', 'date', 'signal', 'price', 
            'current_price', 'timestamp'
        ])
    
    def _save_signals_history(self) -> None:
        """
        Sauvegarde l'historique des signaux dans le fichier.
        """
        try:
            self.signals_history.to_csv(self.signals_file, index=False)
            logger.debug(f"Historique des signaux sauvegardé dans {self.signals_file}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique des signaux: {e}")
    
    def get_signals_summary(self) -> Dict:
        """
        Récupère un résumé des signaux.
        
        Returns:
            Dictionnaire contenant le résumé des signaux
        """
        if self.signals_history.empty:
            return {
                "total_signals": 0,
                "bullish_signals": 0,
                "bearish_signals": 0,
                "latest_signals": []
            }
        
        # Convertir la date en datetime
        self.signals_history['date'] = pd.to_datetime(self.signals_history['date'])
        
        # Trier par date décroissante
        sorted_signals = self.signals_history.sort_values('date', ascending=False)
        
        return {
            "total_signals": len(self.signals_history),
            "bullish_signals": len(self.signals_history[self.signals_history['signal'] == 1]),
            "bearish_signals": len(self.signals_history[self.signals_history['signal'] == -1]),
            "latest_signals": sorted_signals.head(10).to_dict('records')
        }