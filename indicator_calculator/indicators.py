"""
Module pour calculer les indicateurs techniques (ZLMA, EMA).
"""
from typing import Dict, List, Optional, Union, Tuple
import logging
import pandas as pd
import numpy as np

import config

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_CONFIG["format"],
    filename=config.LOG_CONFIG["file"]
)
logger = logging.getLogger(__name__)

class IndicatorCalculator:
    """
    Classe pour calculer les indicateurs techniques.
    """
    
    def __init__(self, ema_period: int = 15, zlma_period: int = 15):
        """
        Initialise le calculateur d'indicateurs.
        
        Args:
            ema_period: Période pour l'EMA
            zlma_period: Période pour le ZLMA
        """
        self.ema_period = ema_period
        self.zlma_period = zlma_period
        logger.info(f"IndicatorCalculator initialisé avec EMA={ema_period}, ZLMA={zlma_period}")
    
    def calculate_ema(self, series: pd.Series, period: int = None) -> pd.Series:
        """
        Calcule l'EMA (Exponential Moving Average).
        
        Args:
            series: Série de prix
            period: Période de l'EMA (utilise self.ema_period si None)
            
        Returns:
            Série contenant l'EMA
        """
        if period is None:
            period = self.ema_period
            
        return series.ewm(span=period, adjust=False).mean()
    
    def calculate_zlma(self, series: pd.Series, period: int = None) -> pd.Series:
        """
        Calcule le ZLMA (Zero-Lag Moving Average).
        
        Args:
            series: Série de prix
            period: Période du ZLMA (utilise self.zlma_period si None)
            
        Returns:
            Série contenant le ZLMA
        """
        if period is None:
            period = self.zlma_period
            
        # Calculer l'EMA
        ema = self.calculate_ema(series, period)
        
        # Calculer la correction pour éliminer le retard
        correction = series + (series - ema)
        
        # Calculer l'EMA de la correction
        zlma = self.calculate_ema(correction, period)
        
        return zlma
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcule les signaux basés sur les croisements EMA/ZLMA.
        
        Args:
            df: DataFrame avec les colonnes EMA et ZLMA
            
        Returns:
            Série contenant les signaux (1: achat, -1: vente, 0: neutre)
        """
        signals = pd.Series(0, index=df.index)
        
        # Vérifier que les colonnes nécessaires existent
        if 'EMA' not in df.columns or 'ZLMA' not in df.columns:
            return signals
            
        # Croisement haussier: ZLMA passe au-dessus de l'EMA
        bullish_cross = (df['ZLMA'] > df['EMA']) & (df['ZLMA'].shift(1) <= df['EMA'].shift(1))
        signals.loc[bullish_cross] = 1
        
        # Croisement baissier: ZLMA passe en-dessous de l'EMA
        bearish_cross = (df['ZLMA'] < df['EMA']) & (df['ZLMA'].shift(1) >= df['EMA'].shift(1))
        signals.loc[bearish_cross] = -1
        
        return signals
    
    def add_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Ajoute tous les indicateurs au DataFrame.
        
        Args:
            data: DataFrame avec les données OHLCV
            
        Returns:
            DataFrame avec les indicateurs ajoutés
        """
        try:
            logger.debug(f"Calcul des indicateurs pour {len(data)} points")
            
            # Créer une copie pour éviter de modifier l'original
            df = data.copy()
            
            # Vérifier que les colonnes nécessaires existent
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in required_columns:
                if col not in df.columns:
                    logger.warning(f"Colonne manquante: {col}")
                    return data  # Retourner les données originales
            
            # Calculer l'EMA
            try:
                df['EMA'] = self.calculate_ema(df['Close'], self.ema_period)
                logger.debug(f"EMA calculé")
            except Exception as e:
                logger.error(f"Erreur lors du calcul de l'EMA: {e}")
                df['EMA'] = np.nan
            
            # Calculer le ZLMA
            try:
                df['ZLMA'] = self.calculate_zlma(df['Close'], self.zlma_period)
                logger.debug(f"ZLMA calculé")
            except Exception as e:
                logger.error(f"Erreur lors du calcul du ZLMA: {e}")
                df['ZLMA'] = np.nan
            
            # Calculer les signaux
            try:
                df['Signal'] = self.calculate_signals(df)
                logger.debug(f"Signaux calculés")
            except Exception as e:
                logger.error(f"Erreur lors du calcul des signaux: {e}")
                df['Signal'] = 0
            
            # Ajouter la tendance
            try:
                # Calculer la tendance basée sur la position relative de ZLMA et EMA
                df['Trend'] = 0  # Neutre par défaut
                df.loc[df['ZLMA'] > df['EMA'], 'Trend'] = 1  # Haussier
                df.loc[df['ZLMA'] < df['EMA'], 'Trend'] = -1  # Baissier
                logger.debug(f"Tendance calculée")
            except Exception as e:
                logger.error(f"Erreur lors du calcul de la tendance: {e}")
                df['Trend'] = 0
            
            return df
            
        except Exception as e:
            logger.error(f"Erreur générale lors du calcul des indicateurs: {e}")
            return data  # Retourner les données originales en cas d'erreur
    
    def get_last_signal(self, data: pd.DataFrame) -> Dict:
        """
        Récupère le dernier signal généré.
        
        Args:
            data: DataFrame avec les indicateurs
            
        Returns:
            Dictionnaire contenant les informations sur le dernier signal
        """
        if data.empty or 'Signal' not in data.columns:
            return {"signal": 0, "date": None, "price": None}
            
        # Filtrer les signaux non nuls
        signals = data[data['Signal'] != 0]
        
        if signals.empty:
            return {
                "signal": 0, 
                "date": data.index[-1].strftime('%Y-%m-%d'),
                "price": float(data['Close'].iloc[-1]),
                "trend": int(data['Trend'].iloc[-1])
            }
            
        # Récupérer le dernier signal
        last_signal = signals.iloc[-1]
        
        return {
            "signal": int(last_signal['Signal']),
            "date": last_signal.name.strftime('%Y-%m-%d'),
            "price": float(last_signal['Close']),
            "trend": int(last_signal['Trend'])
        }
    
    def get_all_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Récupère tous les signaux générés.
        
        Args:
            data: DataFrame avec les indicateurs
            
        Returns:
            DataFrame contenant uniquement les lignes avec des signaux
        """
        if data.empty or 'Signal' not in data.columns:
            return pd.DataFrame()
            
        # Filtrer les signaux non nuls
        signals = data[data['Signal'] != 0].copy()
        
        # Ajouter une colonne descriptive
        signals['SignalType'] = 'Baissier'
        signals.loc[signals['Signal'] == 1, 'SignalType'] = 'Haussier'
        
        return signals