"""
Module pour envoyer des notifications Discord.
"""
from typing import Dict, List, Optional, Union
import logging
import requests
import json
from datetime import datetime
import pytz

import config

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_CONFIG["format"],
    filename=config.LOG_CONFIG["file"]
)
logger = logging.getLogger(__name__)

class DiscordNotifier:
    """
    Classe pour envoyer des notifications Discord.
    """
    
    def __init__(self, webhook_url: str = config.DISCORD_WEBHOOK):
        """
        Initialise le notifier Discord.
        
        Args:
            webhook_url: URL du webhook Discord
        """
        self.webhook_url = webhook_url
        logger.info("DiscordNotifier initialisé")
    
    def send_message(self, content: str, embeds: List[Dict] = None) -> bool:
        """
        Envoie un message Discord.
        
        Args:
            content: Contenu du message
            embeds: Embeds à inclure dans le message
            
        Returns:
            True si le message a été envoyé avec succès, False sinon
        """
        if not self.webhook_url:
            logger.warning("Webhook Discord non configuré")
            return False
            
        payload = {"content": content}
        
        if embeds:
            payload["embeds"] = embeds
            
        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 204:
                logger.info("Message Discord envoyé avec succès")
                return True
            else:
                logger.error(f"Erreur lors de l'envoi du message Discord: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du message Discord: {e}")
            return False
    
    def send_signal_notification(self, ticker: str, signal_data: Dict) -> bool:
        """
        Envoie une notification de signal.
        
        Args:
            ticker: Symbole du ticker
            signal_data: Données du signal
            
        Returns:
            True si la notification a été envoyée avec succès, False sinon
        """
        if not signal_data or "last_signal" not in signal_data or not signal_data["last_signal"]:
            logger.warning(f"Données de signal invalides pour {ticker}")
            return False
            
        last_signal = signal_data["last_signal"]
        signal_type = last_signal["signal"]
        
        if signal_type == 0:
            return False  # Pas de signal à envoyer
            
        # Déterminer le type de signal
        signal_emoji = "🔴" if signal_type == -1 else "🟢"
        signal_text = "VENTE" if signal_type == -1 else "ACHAT"
        signal_color = 0xFF0000 if signal_type == -1 else 0x00FF00
        
        # Créer l'embed
        embed = {
            "title": f"{signal_emoji} Signal de {signal_text} pour {ticker}",
            "color": signal_color,
            "fields": [
                {
                    "name": "Date",
                    "value": last_signal["date"],
                    "inline": True
                },
                {
                    "name": "Prix",
                    "value": f"{last_signal['price']:.2f}",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"TvBin - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        # Ajouter le prix actuel s'il est disponible
        if "last_price" in signal_data and signal_data["last_price"]:
            embed["fields"].append({
                "name": "Prix actuel",
                "value": f"{signal_data['last_price']:.2f}",
                "inline": True
            })
        
        # Envoyer la notification
        return self.send_message(
            content=f"Nouveau signal de {signal_text} détecté pour {ticker}",
            embeds=[embed]
        )
    
    def send_ticker_not_found_alert(self, symbol: str) -> bool:
        """
        Envoie une alerte lorsqu'un ticker n'est pas trouvé.
        
        Args:
            symbol: Symbole de la cryptomonnaie
            
        Returns:
            True si l'alerte a été envoyée avec succès, False sinon
        """
        # Créer l'embed
        embed = {
            "title": f"⚠️ Alerte : Ticker non trouvé",
            "description": f"Le ticker {symbol} n'a pas pu être trouvé sur Binance (ni en USDT, ni en USDC)",
            "color": 0xFFA500,  # Orange
            "fields": [
                {
                    "name": "Ticker",
                    "value": symbol,
                    "inline": True
                },
                {
                    "name": "Date/Heure",
                    "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "inline": True
                }
            ],
            "footer": {
                "text": "TvBin - Vérifiez si ce ticker est disponible sur Binance"
            }
        }
        
        # Envoyer l'alerte
        return self.send_message(
            content=f"⚠️ Alerte : Le ticker {symbol} n'a pas pu être trouvé sur Binance",
            embeds=[embed]
        )