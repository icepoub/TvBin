"""
Service de surveillance pour les cryptomonnaies.
"""
import time
import threading
import logging
import schedule
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any, Optional

import config
from signal_detector.detector import SignalDetector
from discord_notifier.notifier import DiscordNotifier
from data_fetcher.fetcher import DataFetcher

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_CONFIG["format"],
    filename=config.LOG_CONFIG["file"]
)
logger = logging.getLogger(__name__)

class MonitoringService:
    """
    Service de surveillance pour les cryptomonnaies.
    """
    
    def __init__(self, signal_detector: SignalDetector, discord_notifier: DiscordNotifier):
        """
        Initialise le service de surveillance.
        
        Args:
            signal_detector: Instance de SignalDetector
            discord_notifier: Instance de DiscordNotifier
        """
        self.signal_detector = signal_detector
        self.discord_notifier = discord_notifier
        self.data_fetcher = DataFetcher()
        self.is_running = False
        self.monitoring_thread = None
        self.symbols_to_monitor = config.CRYPTO_TICKERS
        self.timeframe = "1d"
        self.last_signals = {}
        self.last_update_time = {}
        self.utc_tz = pytz.timezone('UTC')
        self.setup_schedule()
        logger.info("Service de surveillance initialisé")
    
    def setup_schedule(self):
        """
        Configure les tâches planifiées.
        """
        # Mise à jour des données toutes les 12h
        schedule.every(12).hours.do(self.update_all_crypto_data)
        
        # Vérification des signaux toutes les heures
        schedule.every(1).hours.do(self.check_signals)
        
        # Vérification de l'état du service toutes les 24h
        schedule.every(24).hours.do(self.send_status_report)
        
        logger.info("Tâches planifiées configurées")
    
    def update_all_crypto_data(self):
        """
        Met à jour les données de toutes les cryptomonnaies.
        """
        logger.info("Mise à jour des données de toutes les cryptomonnaies...")
        
        updated_count = 0
        error_count = 0
        
        for symbol in self.symbols_to_monitor:
            try:
                # Vérifier si la mise à jour est nécessaire
                if self._should_update_data(symbol):
                    logger.info(f"Mise à jour des données pour {symbol}...")
                    data = self.data_fetcher.get_ticker_data(symbol, self.timeframe, force_refresh=True)
                    
                    if not data.empty:
                        self.last_update_time[symbol] = datetime.now(self.utc_tz)
                        updated_count += 1
                    else:
                        logger.warning(f"Aucune donnée récupérée pour {symbol}")
                        error_count += 1
                else:
                    logger.debug(f"Pas besoin de mettre à jour les données pour {symbol}")
            except Exception as e:
                logger.error(f"Erreur lors de la mise à jour des données pour {symbol}: {e}")
                error_count += 1
            
            # Pause pour éviter de surcharger l'API
            time.sleep(1)
        
        logger.info(f"Mise à jour terminée: {updated_count} symboles mis à jour, {error_count} erreurs")
    
    def _should_update_data(self, symbol: str) -> bool:
        """
        Détermine si les données d'un symbole doivent être mises à jour.
        
        Args:
            symbol: Symbole de la cryptomonnaie
            
        Returns:
            True si les données doivent être mises à jour, False sinon
        """
        # Si le symbole n'a jamais été mis à jour, le mettre à jour
        if symbol not in self.last_update_time:
            return True
        
        # Calculer le temps écoulé depuis la dernière mise à jour
        now = datetime.now(self.utc_tz)
        elapsed_time = now - self.last_update_time[symbol]
        
        # Mettre à jour si le temps écoulé est supérieur à l'intervalle minimum
        min_interval = timedelta(hours=config.UPDATE_CONFIG["min_update_interval_hours"])
        return elapsed_time > min_interval
    
    def check_signals(self):
        """
        Vérifie les signaux pour toutes les cryptomonnaies.
        """
        logger.info("Vérification des signaux...")
        
        signal_count = 0
        
        for symbol in self.symbols_to_monitor:
            try:
                signals = self.signal_detector.detect_signals(symbol, self.timeframe)
                
                # Vérifier si un nouveau signal a été détecté
                if signals["last_signal"] and signals["last_signal"]["signal"] != 0:
                    current_signal = signals["last_signal"]["signal"]
                    
                    # Vérifier si c'est un nouveau signal
                    if symbol not in self.last_signals or self.last_signals[symbol] != current_signal:
                        self.last_signals[symbol] = current_signal
                        
                        # Envoyer une notification Discord
                        self.discord_notifier.send_signal_notification(symbol, signals)
                        signal_count += 1
                        
                        logger.info(f"Nouveau signal détecté pour {symbol}: {'ACHAT' if current_signal == 1 else 'VENTE'}")
            except Exception as e:
                logger.error(f"Erreur lors de la vérification des signaux pour {symbol}: {e}")
            
            # Pause pour éviter de surcharger le processeur
            time.sleep(0.5)
        
        logger.info(f"Vérification terminée: {signal_count} nouveaux signaux détectés")
    
    def send_status_report(self):
        """
        Envoie un rapport d'état du service.
        """
        try:
            # Récupérer un résumé des signaux
            summary = self.signal_detector.get_signals_summary()
            
            # Créer le message
            message = f"📊 **Rapport d'état TvBin**\n\n"
            message += f"🔍 **Symboles surveillés:** {len(self.symbols_to_monitor)}\n"
            message += f"📈 **Signaux haussiers:** {summary['bullish_signals']}\n"
            message += f"📉 **Signaux baissiers:** {summary['bearish_signals']}\n"
            message += f"📅 **Dernier signal:** {summary['last_signal_date'] or 'Aucun'}\n"
            message += f"⏱️ **Dernière vérification:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            # Envoyer le message
            self.discord_notifier.send_message(message)
            
            logger.info("Rapport d'état envoyé")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du rapport d'état: {e}")
    
    def start(self):
        """
        Démarre le service de surveillance.
        """
        if self.is_running:
            logger.warning("Le service est déjà en cours d'exécution")
            return
        
        self.is_running = True
        self.monitoring_thread = threading.Thread(target=self._run)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        logger.info("Service de surveillance démarré")
        
        # Envoyer une notification de démarrage
        self.discord_notifier.send_message("🚀 **TvBin démarré**\n\nLe service de surveillance des cryptomonnaies est maintenant actif.")
    
    def stop(self):
        """
        Arrête le service de surveillance.
        """
        if not self.is_running:
            logger.warning("Le service n'est pas en cours d'exécution")
            return
        
        self.is_running = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Service de surveillance arrêté")
        
        # Envoyer une notification d'arrêt
        self.discord_notifier.send_message("🛑 **TvBin arrêté**\n\nLe service de surveillance des cryptomonnaies a été arrêté.")
    
    def _run(self):
        """
        Boucle principale du service de surveillance.
        """
        # Exécuter une mise à jour initiale
        self.update_all_crypto_data()
        
        # Exécuter une vérification initiale
        self.check_signals()
        
        while self.is_running:
            try:
                # Exécuter les tâches planifiées
                schedule.run_pending()
                
                # Pause pour éviter de surcharger le processeur
                time.sleep(60)
            except Exception as e:
                logger.error(f"Erreur dans la boucle principale: {e}")
                
                # Pause plus longue en cas d'erreur
                time.sleep(300)