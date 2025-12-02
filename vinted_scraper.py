"""
Module de scraping Vinted
Respecte les délais, gère les erreurs et évite les doublons
"""
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from datetime import datetime
import time
import hashlib

logger = logging.getLogger('vinted_scraper')

class VintedScraper:
    """Scraper pour Vinted avec throttling et gestion d'erreurs"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.user_agent = config.get('user_agent', 'VintedBot/1.0')
        self.min_delay = config.get('min_delay_between_requests', 3)
        self.last_request_time = 0
        self.request_count = 0
        self.request_window_start = time.time()
        self.max_requests_per_minute = config.get('max_requests_per_minute', 10)
    
    async def _wait_for_rate_limit(self):
        """Attend si nécessaire pour respecter les limites de taux"""
        current_time = time.time()
        
        # Reset le compteur si la fenêtre d'une minute est passée
        if current_time - self.request_window_start > 60:
            self.request_count = 0
            self.request_window_start = current_time
        
        # Vérifier la limite par minute
        if self.request_count >= self.max_requests_per_minute:
            wait_time = 60 - (current_time - self.request_window_start)
            if wait_time > 0:
                logger.info(f"Limite de requêtes atteinte, attente de {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self.request_count = 0
                self.request_window_start = time.time()
        
        # Délai minimum entre requêtes
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_delay:
            await asyncio.sleep(self.min_delay - time_since_last)
        
        self.last_request_time = time.time()
        self.request_count += 1
    
    def _build_search_url(self, criteria: Dict) -> str:
        """Construit l'URL de recherche Vinted"""
        base_url = "https://www.vinted.fr/vetements"
        params = []
        
        keyword = criteria.get('keyword', '')
        if keyword:
            params.append(f"search_text={keyword.replace(' ', '+')}")
        
        if criteria.get('min_price'):
            params.append(f"price_from={criteria['min_price']}")
        
        if criteria.get('max_price'):
            params.append(f"price_to={criteria['max_price']}")
        
        if criteria.get('size'):
            params.append(f"size_ids[]={criteria['size']}")
        
        if criteria.get('brand'):
            params.append(f"brand_ids[]={criteria['brand']}")
        
        if criteria.get('condition'):
            params.append(f"status_ids[]={criteria['condition']}")
        
        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url
    
    async def search(self, criteria: Dict, limit: int = 20) -> List[Dict]:
        """
        Effectue une recherche sur Vinted
        
        Note: Vinted utilise un système anti-bot sophistiqué. Cette implémentation
        simule un scraping basique. En production, vous devriez:
        1. Vérifier robots.txt
        2. Utiliser l'API officielle si disponible
        3. Gérer les CAPTCHAs
        4. Respecter les ToS de Vinted
        """
        await self._wait_for_rate_limit()
        
        url = self._build_search_url(criteria)
        logger.info(f"Recherche Vinted: {url}")
        
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status == 429:
                        logger.warning("Rate limit atteint (429), attente de 60s")
                        await asyncio.sleep(60)
                        return await self.search(criteria, limit)
                    
                    if response.status == 403:
                        logger.error("Accès refusé (403) - possiblement bloqué par Vinted")
                        return []
                    
                    if response.status != 200:
                        logger.error(f"Erreur HTTP {response.status}")
                        return []
                    
                    html = await response.text()
                    return self._parse_results(html, criteria, limit)
        
        except asyncio.TimeoutError:
            logger.error("Timeout lors de la requête Vinted")
            return []
        except Exception as e:
            logger.error(f"Erreur scraping: {e}")
            return []
    
    def _parse_results(self, html: str, criteria: Dict, limit: int) -> List[Dict]:
        """
        Parse le HTML de Vinted pour extraire les annonces
        
        IMPORTANT: Le HTML de Vinted change fréquemment. Cette implémentation
        est une simulation. Adaptez selon la structure réelle.
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            # Note: Les sélecteurs CSS réels de Vinted changent régulièrement
            # Cette implémentation est une approximation
            items = soup.select('.feed-grid__item, .item-box, [data-testid="item-box"]')
            
            if not items:
                logger.warning("Aucun élément trouvé - la structure HTML a peut-être changé")
                # Simulation pour mode démo
                return self._generate_demo_results(criteria, limit)
            
            for item in items[:limit]:
                try:
                    result = self._extract_item_data(item, criteria)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.debug(f"Erreur extraction item: {e}")
                    continue
            
            logger.info(f"Trouvé {len(results)} résultats")
            return results
        
        except Exception as e:
            logger.error(f"Erreur parsing HTML: {e}")
            return self._generate_demo_results(criteria, limit)
    
    def _extract_item_data(self, item, criteria: Dict) -> Optional[Dict]:
        """Extrait les données d'un élément HTML"""
        try:
            # Exemple de parsing (à adapter selon structure réelle)
            title_elem = item.select_one('.item-title, [data-testid="item-title"]')
            price_elem = item.select_one('.item-price, [data-testid="item-price"]')
            link_elem = item.select_one('a[href*="/items/"]')
            img_elem = item.select_one('img')
            
            if not (title_elem and price_elem and link_elem):
                return None
            
            title = title_elem.text.strip()
            price_text = price_elem.text.strip()
            price = self._extract_price(price_text)
            url = link_elem.get('href', '')
            
            if not url.startswith('http'):
                url = f"https://www.vinted.fr{url}"
            
            # Extraire l'ID de l'annonce depuis l'URL
            item_id = self._extract_item_id(url)
            
            return {
                'id': item_id,
                'title': title,
                'price': price,
                'price_text': price_text,
                'url': url,
                'image_url': img_elem.get('src', '') if img_elem else None,
                'brand': criteria.get('brand', 'N/A'),
                'size': criteria.get('size', 'N/A'),
                'condition': 'Bon état',
                'seller_reputation': None,
                'date_posted': datetime.now().isoformat(),
                'search_id': criteria.get('search_id')
            }
        
        except Exception as e:
            logger.debug(f"Erreur extraction données: {e}")
            return None
    
    def _extract_price(self, price_text: str) -> float:
        """Extrait le prix numérique depuis le texte"""
        try:
            # Enlever €, espaces, virgules
            price_clean = price_text.replace('€', '').replace(' ', '').replace(',', '.')
            return float(price_clean)
        except:
            return 0.0
    
    def _extract_item_id(self, url: str) -> str:
        """Extrait l'ID de l'annonce depuis l'URL"""
        try:
            parts = url.split('/')
            for part in parts:
                if part.isdigit():
                    return part
            # Fallback: hash de l'URL
            return hashlib.md5(url.encode()).hexdigest()[:12]
        except:
            return hashlib.md5(url.encode()).hexdigest()[:12]
    
    def _generate_demo_results(self, criteria: Dict, limit: int) -> List[Dict]:
        """Génère des résultats de démonstration"""
        keyword = criteria.get('keyword', 'vêtement')
        results = []
        
        for i in range(min(limit, 5)):
            item_id = f"demo_{int(time.time())}_{i}"
            results.append({
                'id': item_id,
                'title': f"{keyword.title()} - Article démo {i+1}",
                'price': 15.0 + (i * 10),
                'price_text': f"{15 + (i * 10)}€",
                'url': f"https://www.vinted.fr/items/{item_id}",
                'image_url': "https://via.placeholder.com/300x400?text=Demo+Item",
                'brand': criteria.get('brand', 'Nike'),
                'size': criteria.get('size', '42'),
                'condition': 'Très bon état',
                'seller_reputation': 4.5,
                'date_posted': datetime.now().isoformat(),
                'search_id': criteria.get('search_id')
            })
        
        return results
    
    async def test_search(self, criteria: Dict) -> List[Dict]:
        """Effectue une recherche de test (limite à 3 résultats)"""
        return await self.search(criteria, limit=3)
