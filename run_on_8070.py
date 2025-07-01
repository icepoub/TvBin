"""
Script pour lancer l'application TvBin sur le port 8070.
"""
import os
import sys
import logging
from web_ui.dashboard import Dashboard

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="tvbin.log"
)
logger = logging.getLogger(__name__)

def main():
    """
    Fonction principale pour lancer l'application sur le port 8070.
    """
    print("Démarrage de l'application TvBin sur le port 8070...")
    logger.info("Démarrage de l'application TvBin sur le port 8070...")
    
    # Créer une instance du dashboard
    dashboard = Dashboard()
    
    # Lancer l'application sur le port fourni par Railway/app
    port = int(os.environ.get("PORT", 8070))
    dashboard.app.run(debug=True, host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()