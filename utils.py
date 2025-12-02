"""
Fonctions utilitaires pour le bot
"""
import discord
from typing import Dict, List
from datetime import datetime
import logging

logger = logging.getLogger('utils')

# Traductions
TRANSLATIONS = {
    'fr': {
        'new_item': 'Nouvel article trouvé !',
        'price': 'Prix',
        'brand': 'Marque',
        'size': 'Taille',
        'condition': 'État',
        'seller': 'Vendeur',
        'view_on_vinted': 'Voir sur Vinted',
        'posted': 'Publié',
        'search_added': 'Recherche ajoutée avec succès !',
        'search_removed': 'Recherche supprimée',
        'no_searches': 'Aucune recherche active',
        'your_searches': 'Vos recherches actives',
        'test_results': 'Résultats de test',
        'error': 'Erreur',
        'search_id': 'ID',
        'keyword': 'Mot-clé',
        'filters': 'Filtres',
        'notifications': 'Notifications'
    },
    'en': {
        'new_item': 'New item found!',
        'price': 'Price',
        'brand': 'Brand',
        'size': 'Size',
        'condition': 'Condition',
        'seller': 'Seller',
        'view_on_vinted': 'View on Vinted',
        'posted': 'Posted',
        'search_added': 'Search added successfully!',
        'search_removed': 'Search removed',
        'no_searches': 'No active searches',
        'your_searches': 'Your active searches',
        'test_results': 'Test results',
        'error': 'Error',
        'search_id': 'ID',
        'keyword': 'Keyword',
        'filters': 'Filters',
        'notifications': 'Notifications'
    }
}

def get_text(key: str, lang: str = 'fr') -> str:
    """Récupère un texte traduit"""
    return TRANSLATIONS.get(lang, TRANSLATIONS['fr']).get(key, key)

def create_item_embed(item: Dict, lang: str = 'fr') -> discord.Embed:
    """Crée un embed Discord pour un article Vinted"""
    embed = discord.Embed(
        title=item['title'][:256],  # Limite Discord
        url=item['url'],
        description=f"**{get_text('price', lang)}:** {item['price_text']}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    # Image
    if item.get('image_url'):
        embed.set_thumbnail(url=item['image_url'])
    
    # Champs d'information
    if item.get('brand') and item['brand'] != 'N/A':
        embed.add_field(name=get_text('brand', lang), value=item['brand'], inline=True)
    
    if item.get('size') and item['size'] != 'N/A':
        embed.add_field(name=get_text('size', lang), value=item['size'], inline=True)
    
    if item.get('condition'):
        embed.add_field(name=get_text('condition', lang), value=item['condition'], inline=True)
    
    if item.get('seller_reputation'):
        embed.add_field(
            name=get_text('seller', lang),
            value=f"⭐ {item['seller_reputation']}/5",
            inline=True
        )
    
    embed.set_footer(text=f"Vinted • {get_text('posted', lang)}")
    
    return embed

def create_search_list_embed(searches: List[Dict], lang: str = 'fr') -> discord.Embed:
    """Crée un embed listant les recherches d'un utilisateur"""
    if not searches:
        embed = discord.Embed(
            title=get_text('your_searches', lang),
            description=get_text('no_searches', lang),
            color=discord.Color.orange()
        )
        return embed
    
    embed = discord.Embed(
        title=get_text('your_searches', lang),
        color=discord.Color.green()
    )
    
    for search in searches[:25]:  # Limite Discord: 25 fields
        filters = []
        
        if search.get('min_price'):
            filters.append(f"Prix min: {search['min_price']}€")
        if search.get('max_price'):
            filters.append(f"Prix max: {search['max_price']}€")
        if search.get('size'):
            filters.append(f"Taille: {search['size']}")
        if search.get('brand'):
            filters.append(f"Marque: {search['brand']}")
        if search.get('condition'):
            filters.append(f"État: {search['condition']}")
        
        dm_status = "✉️ DM" if search.get('dm_notifications') else "📢 Salon"
        
        field_value = f"**{get_text('keyword', lang)}:** {search.get('keyword', 'N/A')}\n"
        if filters:
            field_value += f"**{get_text('filters', lang)}:** {', '.join(filters)}\n"
        field_value += f"**{get_text('notifications', lang)}:** {dm_status}"
        
        embed.add_field(
            name=f"#{search['id']} - {search.get('keyword', 'Recherche')[:50]}",
            value=field_value,
            inline=False
        )
    
    if len(searches) > 25:
        embed.set_footer(text=f"... et {len(searches) - 25} recherches supplémentaires")
    
    return embed

def create_error_embed(message: str, lang: str = 'fr') -> discord.Embed:
    """Crée un embed d'erreur"""
    embed = discord.Embed(
        title=f"❌ {get_text('error', lang)}",
        description=message,
        color=discord.Color.red()
    )
    return embed

def create_success_embed(message: str) -> discord.Embed:
    """Crée un embed de succès"""
    embed = discord.Embed(
        description=f"✅ {message}",
        color=discord.Color.green()
    )
    return embed

def format_search_criteria(search: Dict) -> str:
    """Formate les critères de recherche en texte lisible"""
    parts = [f"Mot-clé: {search.get('keyword', 'N/A')}"]
    
    if search.get('min_price'):
        parts.append(f"Prix min: {search['min_price']}€")
    if search.get('max_price'):
        parts.append(f"Prix max: {search['max_price']}€")
    if search.get('size'):
        parts.append(f"Taille: {search['size']}")
    if search.get('brand'):
        parts.append(f"Marque: {search['brand']}")
    if search.get('condition'):
        parts.append(f"État: {search['condition']}")
    if search.get('location'):
        parts.append(f"Localisation: {search['location']}")
    
    return " | ".join(parts)

class Paginator:
    """Système de pagination pour les longues listes"""
    
    def __init__(self, items: List, per_page: int = 10):
        self.items = items
        self.per_page = per_page
        self.pages = [items[i:i + per_page] for i in range(0, len(items), per_page)]
    
    def get_page(self, page_num: int) -> List:
        """Récupère une page spécifique"""
        if 0 <= page_num < len(self.pages):
            return self.pages[page_num]
        return []
    
    @property
    def total_pages(self) -> int:
        """Nombre total de pages"""
        return len(self.pages)
