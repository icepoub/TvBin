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
            signal_detector: Détecteur de signaux
            discord_notifier: Notifier Discord
        """
        self.signal_detector = signal_detector
        self.discord_notifier = discord_notifier
        self.data_fetcher = DataFetcher()
        self.is_running = False
        self.monitoring_thread = None
        self.symbols_to_monitor = config.CRYPTO_TICKERS
        self.timeframe = "1d"
        self.last_signals = {}
        self.last_update = {}
        self.utc_tz = pytz.timezone('UTC')
        self.setup_schedule()
        logger.info("Service de surveillance initialisé")
    
    def setup_schedule(self):
        """
        Configure les tâches planifiées.
        """
        # Mise à jour des données toutes les 12h
        schedule.every(12).hours.do(self.update_all_data)
        
        # Vérification des signaux toutes les 4h
        schedule.every(4).hours.do(self.check_signals)
        
        # Vérification de l'état du service toutes les 24h
        schedule.every(24).hours.do(self.send_status_report)
        
        logger.info("Tâches planifiées configurées")
    
    def update_all_data(self):
        """
        Met à jour les données pour tous les symboles.
        """
        logger.info("Mise à jour des données pour tous les symboles...")
        
        # Limiter le nombre de requêtes par minute pour éviter les limitations d'API
        max_requests_per_minute = config.UPDATE_CONFIG["max_requests_per_minute"]
        request_count = 0
        
        for symbol in self.symbols_to_monitor:
            try:
                # Vérifier si une mise à jour est nécessaire
                last_update_time = self.last_update.get(symbol)
                now = datetime.now(self.utc_tz)
                
                if (last_update_time is None or 
                    (now - last_update_time) > timedelta(hours=config.UPDATE_CONFIG["min_update_interval_hours"])):
                    
                    # Mettre à jour les données
                    self.data_fetcher.get_ticker_data(symbol, self.timeframe, force_refresh=True)
                    self.last_update[symbol] = now
                    
                    # Incrémenter le compteur de requêtes
                    request_count += 1
                    
                    # Pause si on atteint la limite de requêtes par minute
                    if request_count >= max_requests_per_minute:
                        logger.info(f"Pause de 60 secondes après {request_count} requêtes")
                        time.sleep(60)
                        request_count = 0
                    else:
                        # Petite pause entre les requêtes pour éviter de surcharger l'API
                        time.sleep(1)
            except Exception as e:
                logger.error(f"Erreur lors de la mise à jour des données pour {symbol}: {e}")
        
        logger.info("Mise à jour des données terminée")
    
    def check_signals(self):
        """
        Vérifie les signaux pour tous les symboles.
        """
        logger.info("Vérification des signaux pour tous les symboles...")
        
        for symbol in self.symbols_to_monitor:
            try:
                # Détecter les signaux
                signals = self.signal_detector.detect_signals(symbol, self.timeframe)
                
                # Vérifier si le signal a changé
                if (symbol in self.last_signals and 
                    signals["last_signal"] != self.last_signals.get(symbol)):
                    
                    self.last_signals[symbol] = signals["last_signal"]
                    
                    # Envoyer une notification si le signal est non nul
                    if signals["last_signal"] and signals["last_signal"]["signal"] != 0:
                        self.discord_notifier.send_signal_notification(symbol, signals)
                
                # Stocker le dernier signal
                self.last_signals[symbol] = signals["last_signal"]
                
                # Petite pause entre les vérifications pour éviter de surcharger le processeur
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Erreur lors de la vérification des signaux pour {symbol}: {e}")
        
        logger.info("Vérification des signaux terminée")
    
    def send_status_report(self):
        """
        Envoie un rapport d'état du service.
        """
        try:
            # Récupérer un résumé des signaux
            summary = self.signal_detector.get_signals_summary()
            
            # Créer le message
            message = f"📊 **Rapport d'état TvBin**\n\n"
            message += f"🕒 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"📈 Signaux haussiers: {summary['bullish_signals']}\n"
            message += f"📉 Signaux baissiers: {summary['bearish_signals']}\n"
            message += f"🔢 Total des signaux: {summary['total_signals']}\n"
            message += f"🔍 Symboles surveillés: {len(self.symbols_to_monitor)}\n"
            
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
        try:
            self.discord_notifier.send_message("🚀 **Service TvBin démarré**")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification de démarrage: {e}")
    
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
        try:
            self.discord_notifier.send_message("🛑 **Service TvBin arrêté**")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification d'arrêt: {e}")
    
    def _run(self):
        """
        Boucle principale du service de surveillance.
        """
        # Exécuter une mise à jour initiale
        self.update_all_data()
        self.check_signals()
        
        while self.is_running:
            try:
                # Exécuter les tâches planifiées
                schedule.run_pending()
                
                # Pause pour éviter de surcharger le processeur
                time.sleep(60)
            except Exception as e:
                logger.error(f"Erreur dans la boucle principale du service: {e}")
                time.sleep(300)  # Pause plus longue en cas d'erreur