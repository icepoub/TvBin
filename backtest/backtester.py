"""
Module pour le backtesting des stratégies de trading.
"""
from typing import Dict, List, Optional, Union, Tuple
import logging
import os
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

import config
from data_fetcher.fetcher import DataFetcher
from indicator_calculator.indicators import IndicatorCalculator
from signal_detector.detector import SignalDetector

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_CONFIG["format"],
    filename=config.LOG_CONFIG["file"]
)
logger = logging.getLogger(__name__)

class Backtester:
    """
    Classe pour le backtesting des stratégies de trading.
    """
    
    def __init__(
        self,
        data_fetcher: Optional[DataFetcher] = None,
        signal_detector: Optional[SignalDetector] = None,
        indicator_calculator: Optional[IndicatorCalculator] = None,
        save_dir: Path = config.DATA_DIR,
        initial_capital: float = config.BACKTEST_CONFIG["initial_capital"],
        position_size_pct: float = config.BACKTEST_CONFIG["position_size_pct"],
        stop_loss_pct: float = config.BACKTEST_CONFIG["stop_loss_pct"],
        take_profit_pct: float = config.BACKTEST_CONFIG["take_profit_pct"]
    ):
        """
        Initialise le backtester.
        
        Args:
            data_fetcher: Instance de DataFetcher
            signal_detector: Instance de SignalDetector
            indicator_calculator: Instance de IndicatorCalculator
            save_dir: Répertoire pour sauvegarder les résultats
            initial_capital: Capital initial pour le backtesting
            position_size_pct: Pourcentage du capital à utiliser par position
            stop_loss_pct: Pourcentage de stop loss
            take_profit_pct: Pourcentage de take profit
        """
        self.data_fetcher = data_fetcher or DataFetcher()
        self.indicator_calculator = indicator_calculator or IndicatorCalculator()
        self.signal_detector = signal_detector or SignalDetector(
            data_fetcher=self.data_fetcher,
            indicator_calculator=self.indicator_calculator
        )
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
        self.results_file = self.save_dir / config.SAVE_CONFIG["backtest_file"]
        logger.info("Backtester initialisé")
    
    def run_backtest(self, ticker: str, timeframe: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
        """
        Exécute un backtest pour un ticker et un timeframe donnés.
        
        Args:
            ticker: Symbole de la cryptomonnaie
            timeframe: Timeframe à utiliser
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)
            
        Returns:
            Dictionnaire contenant les résultats du backtest
        """
        logger.info(f"Démarrage du backtest pour {ticker} sur {timeframe}")
        
        try:
            # Vérifier si les données sont déjà en cache
            cache_file = self.save_dir / f"{ticker}_{timeframe}_data.parquet"
            
            if os.path.exists(cache_file):
                logger.info(f"Chargement des données depuis le cache pour {ticker}")
                try:
                    data = pd.read_parquet(cache_file)
                except Exception as e:
                    logger.warning(f"Erreur lors du chargement du cache pour {ticker}: {e}")
                    # Si erreur de lecture du cache, on supprime le fichier corrompu
                    os.remove(cache_file)
                    data = self.data_fetcher.get_ticker_data(ticker, timeframe)
            else:
                # Récupérer les données historiques
                data = self.data_fetcher.get_ticker_data(ticker, timeframe)
                
            if data.empty:
                logger.warning(f"Aucune donnée disponible pour {ticker} sur {timeframe}")
                return {"success": False, "error": "Aucune donnée disponible"}
                
            # Vérifier que les colonnes requises sont présentes
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                error_msg = f"Colonnes manquantes dans les données: {', '.join(missing_columns)}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
                
            # Sauvegarder les données en cache (seulement si elles ne sont pas déjà en cache)
            if not os.path.exists(cache_file):
                try:
                    data.to_parquet(cache_file)
                    logger.info(f"Données sauvegardées en cache pour {ticker}")
                except Exception as e:
                    logger.warning(f"Erreur lors de la sauvegarde du cache pour {ticker}: {e}")
            
            # Filtrer les données par date si nécessaire
            if start_date:
                data = data[data.index >= start_date]
            if end_date:
                data = data[data.index <= end_date]
            
            # Calculer les indicateurs
            data_with_indicators = self.indicator_calculator.add_indicators(data)
            
            # Détecter les signaux
            signals = pd.DataFrame(index=data_with_indicators.index)
            signals['signal'] = 0
            
            # Calculer les signaux une seule fois pour toutes les données
            signal_result = self.signal_detector.detect_signals(ticker, timeframe)
            if signal_result:
                # Récupérer les signaux directement depuis l'IndicatorCalculator
                signals_df = self.indicator_calculator.get_all_signals(data_with_indicators)
                if not signals_df.empty:
                    # Copier les signaux dans notre DataFrame
                    signals.loc[signals_df.index, 'signal'] = signals_df['Signal']
            
            # Exécuter la simulation de trading
            results = self._simulate_trading(data, signals)
            
            # Sauvegarder les résultats
            self._save_results(ticker, timeframe, results)
            
            logger.info(f"Backtest terminé pour {ticker} sur {timeframe}")
            return {"success": True, "results": results}
            
        except Exception as e:
            logger.error(f"Erreur lors du backtest pour {ticker} sur {timeframe}: {e}")
            return {"success": False, "error": str(e)}
    
    def _simulate_trading(self, data: pd.DataFrame, signals: pd.DataFrame) -> Dict:
        """
        Simule le trading basé sur les signaux.
        Stratégie long-only : entre sur signal haussier, sort sur signal baissier.
        
        Args:
            data: DataFrame contenant les données historiques
            signals: DataFrame contenant les signaux
            
        Returns:
            Dictionnaire contenant les résultats de la simulation
        """
        # Fusionner les données et les signaux
        trading_data = data.copy()
        trading_data = trading_data.join(signals[["signal"]], how="left")
        trading_data["signal"] = trading_data["signal"].fillna(0)
        
        # Initialiser les variables de simulation
        capital = self.initial_capital
        position = 0
        entry_price = 0
        trades = []
        
        # Parcourir les données
        for i, row in trading_data.iterrows():
            current_price = row["Close"]
            current_signal = row["signal"]
            
            # Si nous avons une position ouverte et un signal baissier (-1), nous sortons
            if position > 0 and current_signal == -1:
                # Calculer le P&L
                pnl = position * (current_price - entry_price)
                capital += pnl
                
                # Mettre à jour le dernier trade avec les informations de sortie
                trades[-1].update({
                    "date_exit": i,
                    "price_exit": current_price,
                    "pnl": pnl,
                    "pnl_pct": (pnl / (position * entry_price)) * 100,
                    "capital": capital
                })
                
                # Fermer la position
                position = 0
                entry_price = 0
            
            # Si nous n'avons pas de position et un signal haussier (1), nous entrons
            elif position == 0 and current_signal == 1:
                # Calculer la taille de la position
                position_size = capital * self.position_size_pct
                position = position_size / current_price
                entry_price = current_price
                
                # Enregistrer le trade avec tous les champs possibles
                trades.append({
                    "date_entry": i,
                    "price_entry": entry_price,
                    "position": position,
                    "direction": "LONG",
                    "date_exit": None,
                    "price_exit": None,
                    "pnl": None,
                    "pnl_pct": None,
                    "capital": capital
                })
        
        # Fermer la position si elle est encore ouverte à la fin
        if position > 0:
            current_price = trading_data.iloc[-1]["Close"]
            pnl = position * (current_price - entry_price)
            capital += pnl
            
            # Mettre à jour le dernier trade avec les informations de sortie
            trades[-1].update({
                "date_exit": trading_data.index[-1],
                "price_exit": current_price,
                "pnl": pnl,
                "pnl_pct": (pnl / (position * entry_price)) * 100,
                "capital": capital
            })
        
        # Calculer les statistiques
        if trades:
            trades_df = pd.DataFrame(trades)
            winning_trades = trades_df[trades_df["pnl"] > 0] if "pnl" in trades_df.columns else pd.DataFrame()
            losing_trades = trades_df[trades_df["pnl"] < 0] if "pnl" in trades_df.columns else pd.DataFrame()
            
            stats = {
                "initial_capital": self.initial_capital,
                "final_capital": capital,
                "total_return": (capital / self.initial_capital - 1) * 100,
                "total_trades": len(trades),
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "win_rate": len(winning_trades) / len(trades) * 100 if trades else 0,
                "avg_win": winning_trades["pnl"].mean() if not winning_trades.empty else 0,
                "avg_loss": losing_trades["pnl"].mean() if not losing_trades.empty else 0,
                "max_drawdown": self._calculate_max_drawdown(trades_df) if "capital" in trades_df.columns else 0,
                "trades": trades
            }
        else:
            stats = {
                "initial_capital": self.initial_capital,
                "final_capital": capital,
                "total_return": 0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "max_drawdown": 0,
                "trades": []
            }
        
        return stats
    
    def _calculate_max_drawdown(self, trades_df: pd.DataFrame) -> float:
        """
        Calcule le drawdown maximum.
        
        Args:
            trades_df: DataFrame contenant les trades
            
        Returns:
            Drawdown maximum en pourcentage
        """
        if "capital" not in trades_df.columns or trades_df.empty:
            return 0
        
        # Calculer le drawdown pour chaque trade
        peak = self.initial_capital
        drawdowns = []
        
        for _, row in trades_df.iterrows():
            if "capital" in row:
                current_capital = row["capital"]
                peak = max(peak, current_capital)
                drawdown = (peak - current_capital) / peak * 100
                drawdowns.append(drawdown)
        
        return max(drawdowns) if drawdowns else 0
    
    def _save_results(self, ticker: str, timeframe: str, results: Dict) -> None:
        """
        Sauvegarde les résultats du backtest.
        
        Args:
            ticker: Symbole de la cryptomonnaie
            timeframe: Timeframe utilisé
            results: Résultats du backtest
        """
        try:
            # Créer un DataFrame avec les résultats
            results_summary = {
                "ticker": ticker,
                "timeframe": timeframe,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "initial_capital": results["initial_capital"],
                "final_capital": results["final_capital"],
                "total_return": results["total_return"],
                "total_trades": results["total_trades"],
                "winning_trades": results["winning_trades"],
                "losing_trades": results["losing_trades"],
                "win_rate": results["win_rate"],
                "max_drawdown": results["max_drawdown"]
            }
            
            results_df = pd.DataFrame([results_summary])
            
            # Sauvegarder ou ajouter au fichier existant
            if os.path.exists(self.results_file):
                existing_results = pd.read_csv(self.results_file)
                updated_results = pd.concat([existing_results, results_df], ignore_index=True)
                updated_results.to_csv(self.results_file, index=False)
            else:
                results_df.to_csv(self.results_file, index=False)
                
            logger.info(f"Résultats du backtest sauvegardés pour {ticker} sur {timeframe}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des résultats du backtest: {e}")
    
    def get_backtest_results(self, ticker: Optional[str] = None) -> pd.DataFrame:
        """
        Récupère les résultats des backtests.
        
        Args:
            ticker: Filtrer par ticker (optionnel)
            
        Returns:
            DataFrame contenant les résultats des backtests
        """
        try:
            if not os.path.exists(self.results_file):
                logger.warning("Aucun résultat de backtest disponible")
                return pd.DataFrame()
            
            results = pd.read_csv(self.results_file)
            
            if ticker:
                results = results[results["ticker"] == ticker]
                
            return results
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des résultats de backtest: {e}")
            return pd.DataFrame() 