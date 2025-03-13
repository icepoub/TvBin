"""
Gestionnaire de liste de surveillance pour les cryptomonnaies.
"""
from typing import Dict, List, Optional, Union, Any
import logging
import os
import json
from datetime import datetime
from pathlib import Path

import config
from data_fetcher.fetcher import DataFetcher
from signal_detector.detector import SignalDetector
from discord_notifier.notifier import DiscordNotifier

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_CONFIG["format"],
    filename=config.LOG_CONFIG["file"]
)
logger = logging.getLogger(__name__)

class WatchlistManager:
    """
    Classe pour gérer la liste de surveillance des cryptomonnaies.
    """
    
    def __init__(
        self,
        data_fetcher: Optional[DataFetcher] = None,
        signal_detector: Optional[SignalDetector] = None,
        discord_notifier: Optional[DiscordNotifier] = None,
        save_dir: Path = config.DATA_DIR
    ):
        """
        Initialise le gestionnaire de liste de surveillance.
        
        Args:
            data_fetcher: Instance de DataFetcher
            signal_detector: Instance de SignalDetector
            discord_notifier: Instance de DiscordNotifier
            save_dir: Répertoire pour sauvegarder la liste de surveillance
        """
        self.data_fetcher = data_fetcher or DataFetcher()
        self.signal_detector = signal_detector or SignalDetector()
        self.discord_notifier = discord_notifier or DiscordNotifier()
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        
        self.watchlist_file = self.save_dir / "watchlist.json"
        self.alerts_log_file = self.save_dir / "watchlist_alerts.json"
        
        # Structure de la liste de surveillance:
        # {
        #     "ticker1": {
        #         "timeframe": "1d",
        #         "notifications_enabled": True,
        #         "last_signal": 0,  # 0: pas de signal, 1: haussier, -1: baissier
        #         "last_signal_date": "2023-01-01 12:00:00"
        #     },
        #     ...
        # }
        self.watchlist = self._load_watchlist()
        
        # Structure du journal des alertes:
        # {
        #     "ticker1_1d": {
        #         "last_alert_signal": 1,
        #         "last_alert_date": "2023-01-01 12:00:00"
        #     },
        #     ...
        # }
        self.alerts_log = self._load_alerts_log()
        
        logger.info("WatchlistManager initialisé")
    
    def _load_watchlist(self) -> Dict[str, Dict[str, Any]]:
        """
        Charge la liste de surveillance depuis le fichier JSON.
        
        Returns:
            Dictionnaire contenant la liste de surveillance
        """
        if not os.path.exists(self.watchlist_file):
            return {}
        
        try:
            with open(self.watchlist_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la liste de surveillance: {e}")
            return {}
    
    def _save_watchlist(self) -> None:
        """
        Sauvegarde la liste de surveillance dans le fichier JSON.
        """
        try:
            with open(self.watchlist_file, "w") as f:
                json.dump(self.watchlist, f, indent=4)
            logger.info("Liste de surveillance sauvegardée")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la liste de surveillance: {e}")
    
    def _load_alerts_log(self) -> Dict[str, Dict[str, Any]]:
        """
        Charge le journal des alertes depuis le fichier JSON.
        
        Returns:
            Dictionnaire contenant le journal des alertes
        """
        if not os.path.exists(self.alerts_log_file):
            return {}
        
        try:
            with open(self.alerts_log_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erreur lors du chargement du journal des alertes: {e}")
            return {}
    
    def _save_alerts_log(self) -> None:
        """
        Sauvegarde le journal des alertes dans le fichier JSON.
        """
        try:
            with open(self.alerts_log_file, "w") as f:
                json.dump(self.alerts_log, f, indent=4)
            logger.debug("Journal des alertes sauvegardé")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du journal des alertes: {e}")
    
    def add_to_watchlist(self, ticker: str, timeframe: str = "1d", notifications_enabled: bool = True) -> bool:
        """
        Ajoute un ticker à la liste de surveillance.
        
        Args:
            ticker: Symbole de la cryptomonnaie
            timeframe: Timeframe à surveiller ("1d" ou "1w")
            notifications_enabled: Activer les notifications Discord
            
        Returns:
            True si le ticker a été ajouté avec succès, False sinon
        """
        if timeframe not in ["1d", "1w"]:
            logger.error(f"Timeframe invalide: {timeframe}")
            return False
        
        # Vérifier si le ticker existe
        try:
            data = self.data_fetcher.get_ticker_data(ticker, timeframe)
            if data.empty:
                logger.warning(f"Aucune donnée disponible pour {ticker} sur {timeframe}")
                return False
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données pour {ticker}: {e}")
            return False
        
        # Ajouter le ticker à la liste de surveillance
        self.watchlist[ticker] = {
            "timeframe": timeframe,
            "notifications_enabled": notifications_enabled,
            "last_signal": 0,
            "last_signal_date": ""
        }
        
        # Sauvegarder la liste de surveillance
        self._save_watchlist()
        
        logger.info(f"Ticker {ticker} ajouté à la liste de surveillance sur {timeframe}")
        return True
    
    def remove_from_watchlist(self, ticker: str) -> bool:
        """
        Supprime un ticker de la liste de surveillance.
        
        Args:
            ticker: Symbole de la cryptomonnaie
            
        Returns:
            True si le ticker a été supprimé avec succès, False sinon
        """
        if ticker not in self.watchlist:
            logger.warning(f"Ticker {ticker} non trouvé dans la liste de surveillance")
            return False
        
        # Supprimer le ticker de la liste de surveillance
        del self.watchlist[ticker]
        
        # Sauvegarder la liste de surveillance
        self._save_watchlist()
        
        logger.info(f"Ticker {ticker} supprimé de la liste de surveillance")
        return True
    
    def toggle_notifications(self, ticker: str) -> bool:
        """
        Active ou désactive les notifications pour un ticker.
        
        Args:
            ticker: Symbole de la cryptomonnaie
            
        Returns:
            True si les notifications ont été modifiées avec succès, False sinon
        """
        if ticker not in self.watchlist:
            logger.warning(f"Ticker {ticker} non trouvé dans la liste de surveillance")
            return False
        
        # Inverser l'état des notifications
        self.watchlist[ticker]["notifications_enabled"] = not self.watchlist[ticker]["notifications_enabled"]
        
        # Sauvegarder la liste de surveillance
        self._save_watchlist()
        
        status = "activées" if self.watchlist[ticker]["notifications_enabled"] else "désactivées"
        logger.info(f"Notifications {status} pour {ticker}")
        return True
    
    def get_watchlist(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère la liste de surveillance.
        
        Returns:
            Dictionnaire contenant la liste de surveillance
        """
        return self.watchlist
    
    def check_watchlist_signals(self) -> List[Dict[str, Any]]:
        """
        Vérifie les signaux pour tous les tickers de la liste de surveillance.
        
        Returns:
            Liste des nouveaux signaux détectés
        """
        logger.info("Vérification des signaux pour la liste de surveillance...")
        
        new_signals = []
        
        for ticker, info in self.watchlist.items():
            try:
                timeframe = info["timeframe"]
                
                # Détecter les signaux
                signals = self.signal_detector.detect_signals(ticker, timeframe)
                
                if signals["last_signal"] and signals["last_signal"]["signal"] != 0:
                    current_signal = signals["last_signal"]["signal"]
                    current_date = signals["last_signal"]["date"]
                    
                    # Vérifier si c'est un nouveau signal
                    if info["last_signal"] != current_signal:
                        # Mettre à jour la liste de surveillance
                        self.watchlist[ticker]["last_signal"] = current_signal
                        self.watchlist[ticker]["last_signal_date"] = current_date
                        
                        # Vérifier si les notifications sont activées
                        if info["notifications_enabled"]:
                            # Vérifier si une alerte a déjà été envoyée pour ce signal
                            ticker_key = f"{ticker}_{timeframe}"
                            if ticker_key not in self.alerts_log or \
                               self.alerts_log[ticker_key]["last_alert_signal"] != current_signal:
                                
                                # Envoyer une notification Discord
                                self._send_signal_notification(ticker, timeframe, current_signal, current_date)
                                
                                # Mettre à jour le journal des alertes
                                self.alerts_log[ticker_key] = {
                                    "last_alert_signal": current_signal,
                                    "last_alert_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }
                                self._save_alerts_log()
                        
                        # Ajouter le signal à la liste des nouveaux signaux
                        new_signals.append({
                            "ticker": ticker,
                            "timeframe": timeframe,
                            "signal": current_signal,
                            "date": current_date
                        })
                        
                        logger.info(f"Nouveau signal détecté pour {ticker} sur {timeframe}: {'ACHAT' if current_signal == 1 else 'VENTE'}")
            except Exception as e:
                logger.error(f"Erreur lors de la vérification des signaux pour {ticker}: {e}")
        
        # Sauvegarder la liste de surveillance
        self._save_watchlist()
        
        logger.info(f"Vérification terminée: {len(new_signals)} nouveaux signaux détectés")
        return new_signals
    
    def _send_signal_notification(self, ticker: str, timeframe: str, signal: int, date: str) -> None:
        """
        Envoie une notification Discord pour un signal.
        
        Args:
            ticker: Symbole de la cryptomonnaie
            timeframe: Timeframe du signal
            signal: Type de signal (1: haussier, -1: baissier)
            date: Date du signal
        """
        try:
            # Créer le message
            signal_type = "HAUSSIER 📈" if signal == 1 else "BAISSIER 📉"
            timeframe_str = "journalier" if timeframe == "1d" else "hebdomadaire"
            
            message = f"🚨 **Alerte de la Liste de Surveillance** 🚨\n\n"
            message += f"**Ticker:** {ticker}\n"
            message += f"**Timeframe:** {timeframe_str}\n"
            message += f"**Signal:** {signal_type}\n"
            message += f"**Date:** {date}\n"
            
            # Envoyer le message
            self.discord_notifier.send_message(message)
            
            logger.info(f"Notification envoyée pour {ticker} sur {timeframe}")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification pour {ticker}: {e}")
    
    def update_signal(self, ticker: str, signal: int, signal_date: str) -> bool:
        """
        Met à jour le dernier signal et sa date pour un ticker donné.
        
        Args:
            ticker (str): Le ticker à mettre à jour
            signal (int): Le nouveau signal (-1, 0, ou 1)
            signal_date (str): La date du signal au format YYYY-MM-DD
            
        Returns:
            bool: True si la mise à jour a réussi, False sinon
        """
        try:
            if ticker in self.watchlist:
                self.watchlist[ticker]["last_signal"] = signal
                self.watchlist[ticker]["last_signal_date"] = signal_date
                self._save_watchlist()
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du signal pour {ticker}: {e}")
            return False