"""
Point d'entrée principal du bot Discord Vinted
"""
import asyncio
import sys
import argparse
from discord_bot import VintedBot
from storage import Storage
import logging

def setup_logging(log_level: str = "INFO"):
    """Configure le système de logging"""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler('bot.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

async def main(demo_mode: bool = False):
    """Fonction principale"""
    logger = logging.getLogger('main')
    
    try:
        # Charger la configuration
        storage = Storage()
        config = await storage.load_config()
        
        setup_logging(config.get('log_level', 'INFO'))
        logger.info("Démarrage du bot Vinted Discord...")
        
        # Vérifier le token
        if not config.get('token') or config['token'] == "VOTRE_TOKEN_DISCORD_ICI":
            logger.error("Token Discord manquant dans config.json!")
            logger.error("Copiez config.json.example vers config.json et ajoutez votre token.")
            return
        
        # Créer et démarrer le bot
        bot = VintedBot(config, demo_mode=demo_mode)
        await bot.start(config['token'])
        
    except KeyboardInterrupt:
        logger.info("Arrêt du bot (Ctrl+C)...")
    except Exception as e:
        logger.error(f"Erreur critique: {e}", exc_info=True)
    finally:
        logger.info("Bot arrêté.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Bot Discord Vinted')
    parser.add_argument('--demo', action='store_true', 
                       help='Lancer en mode démo (utilise demo_results.json)')
    args = parser.parse_args()
    
    # Exécuter le bot
    try:
        asyncio.run(main(demo_mode=args.demo))
    except KeyboardInterrupt:
        print("\nArrêt du bot...")
