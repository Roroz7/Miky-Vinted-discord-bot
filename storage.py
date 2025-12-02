"""
Gestion du stockage JSON avec verrouillage pour éviter les corruptions
"""
import json
import asyncio
import aiofiles
from typing import Any, Dict, List
from pathlib import Path
import logging

logger = logging.getLogger('storage')

class Storage:
    """Gestionnaire de stockage JSON avec locks"""
    
    def __init__(self):
        self.locks = {
            'config': asyncio.Lock(),
            'searches': asyncio.Lock(),
            'cache': asyncio.Lock(),
            'users': asyncio.Lock()
        }
        self._ensure_files_exist()
    
    def _ensure_files_exist(self):
        """Crée les fichiers JSON s'ils n'existent pas"""
        files = {
            'config.json': {},
            'searches.json': [],
            'results_cache.json': {},
            'users.json': {}
        }
        
        for filename, default_content in files.items():
            path = Path(filename)
            if not path.exists():
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(default_content, f, indent=2, ensure_ascii=False)
                logger.info(f"Fichier {filename} créé avec contenu par défaut")
    
    async def _read_json(self, filename: str) -> Any:
        """Lit un fichier JSON de manière asynchrone"""
        try:
            async with aiofiles.open(filename, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except FileNotFoundError:
            logger.warning(f"Fichier {filename} introuvable, retour valeur par défaut")
            return {} if filename != 'searches.json' else []
        except json.JSONDecodeError as e:
            logger.error(f"Erreur JSON dans {filename}: {e}")
            return {} if filename != 'searches.json' else []
    
    async def _write_json(self, filename: str, data: Any):
        """Écrit un fichier JSON de manière asynchrone"""
        try:
            async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Erreur écriture {filename}: {e}")
            raise
    
    async def load_config(self) -> Dict:
        """Charge la configuration"""
        async with self.locks['config']:
            return await self._read_json('config.json')
    
    async def save_config(self, config: Dict):
        """Sauvegarde la configuration"""
        async with self.locks['config']:
            await self._write_json('config.json', config)
    
    async def load_searches(self) -> List[Dict]:
        """Charge toutes les recherches"""
        async with self.locks['searches']:
            return await self._read_json('searches.json')
    
    async def save_searches(self, searches: List[Dict]):
        """Sauvegarde toutes les recherches"""
        async with self.locks['searches']:
            await self._write_json('searches.json', searches)
    
    async def add_search(self, search: Dict) -> Dict:
        """Ajoute une recherche"""
        searches = await self.load_searches()
        
        # Générer ID unique
        max_id = max([s.get('id', 0) for s in searches], default=0)
        search['id'] = max_id + 1
        
        searches.append(search)
        await self.save_searches(searches)
        return search
    
    async def remove_search(self, search_id: int, user_id: int) -> bool:
        """Supprime une recherche (seulement si elle appartient à l'utilisateur)"""
        searches = await self.load_searches()
        original_len = len(searches)
        
        searches = [s for s in searches if not (s['id'] == search_id and s['user_id'] == user_id)]
        
        if len(searches) < original_len:
            await self.save_searches(searches)
            return True
        return False
    
    async def get_user_searches(self, user_id: int) -> List[Dict]:
        """Récupère les recherches d'un utilisateur"""
        searches = await self.load_searches()
        return [s for s in searches if s['user_id'] == user_id]
    
    async def get_search_by_id(self, search_id: int) -> Dict | None:
        """Récupère une recherche par ID"""
        searches = await self.load_searches()
        return next((s for s in searches if s['id'] == search_id), None)
    
    async def load_cache(self) -> Dict:
        """Charge le cache des résultats"""
        async with self.locks['cache']:
            return await self._read_json('results_cache.json')
    
    async def save_cache(self, cache: Dict):
        """Sauvegarde le cache"""
        async with self.locks['cache']:
            await self._write_json('results_cache.json', cache)
    
    async def is_result_cached(self, item_id: str) -> bool:
        """Vérifie si un résultat est en cache"""
        cache = await self.load_cache()
        return item_id in cache
    
    async def add_to_cache(self, item_id: str, timestamp: float):
        """Ajoute un résultat au cache"""
        cache = await self.load_cache()
        cache[item_id] = timestamp
        await self.save_cache(cache)
    
    async def clean_old_cache(self, max_age_hours: int = 24):
        """Nettoie les entrées de cache trop anciennes"""
        import time
        cache = await self.load_cache()
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        cleaned_cache = {
            k: v for k, v in cache.items()
            if (current_time - v) < max_age_seconds
        }
        
        if len(cleaned_cache) < len(cache):
            await self.save_cache(cleaned_cache)
            logger.info(f"Cache nettoyé: {len(cache) - len(cleaned_cache)} entrées supprimées")
    
    async def load_users(self) -> Dict:
        """Charge les préférences utilisateurs"""
        async with self.locks['users']:
            return await self._read_json('users.json')
    
    async def save_users(self, users: Dict):
        """Sauvegarde les préférences utilisateurs"""
        async with self.locks['users']:
            await self._write_json('users.json', users)
    
    async def get_user_prefs(self, user_id: int) -> Dict:
        """Récupère les préférences d'un utilisateur"""
        users = await self.load_users()
        user_key = str(user_id)
        return users.get(user_key, {})
    
    async def update_user_prefs(self, user_id: int, prefs: Dict):
        """Met à jour les préférences d'un utilisateur"""
        users = await self.load_users()
        user_key = str(user_id)
        users[user_key] = prefs
        await self.save_users(users)
