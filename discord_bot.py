"""
Bot Discord principal avec commandes et gestion des événements
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from typing import Optional, Dict, List
import logging
from datetime import datetime
import time

from storage import Storage
from vinted_scraper import VintedScraper
from utils import (
    create_item_embed, create_search_list_embed,
    create_error_embed, create_success_embed,
    get_text, format_search_criteria
)

logger = logging.getLogger('discord_bot')


class VintedBot(commands.Bot):
    """Bot Discord pour Vinted"""

    def __init__(self, config: Dict, demo_mode: bool = False):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=config.get('prefix', '/'),
            intents=intents,
            help_command=None
        )

        self.config = config
        self.storage = Storage()
        self.scraper = VintedScraper(config)
        self.demo_mode = demo_mode
        self.lang = config.get('language', 'fr')

        # Statistiques
        self.stats = {
            'searches_run': 0,
            'items_found': 0,
            'notifications_sent': 0
        }

    async def setup_hook(self):
        """Configuration initiale du bot"""
        await self.add_cog(VintedCommands(self))
        await self.tree.sync()
        logger.info("Commandes slash synchronisées")

        if not self.demo_mode:
            self.scraping_loop.start()
            logger.info("Boucle de scraping démarrée")

    async def on_ready(self):
        """Événement: bot prêt"""
        logger.info(f"Bot connecté en tant que {self.user} (ID: {self.user.id})")
        logger.info(f"Mode démo: {self.demo_mode}")

        if self.demo_mode:
            await self.run_demo()

    async def on_command_error(self, ctx, error):
        """Gestion globale des erreurs de commandes"""
        if isinstance(error, commands.CommandNotFound):
            return

        logger.error(f"Erreur commande: {error}")

        if ctx.interaction:
            await ctx.interaction.response.send_message(
                embed=create_error_embed(str(error), self.lang),
                ephemeral=True
            )

    @tasks.loop(seconds=90)
    async def scraping_loop(self):
        """Boucle principale de scraping"""
        try:
            interval = self.config.get('scraping_interval', 90)
            self.scraping_loop.change_interval(seconds=interval)

            logger.info("Début du cycle de scraping...")
            searches = await self.storage.load_searches()
            active_searches = [s for s in searches if s.get('enabled', True)]

            logger.info(f"{len(active_searches)} recherches actives à traiter")

            for search in active_searches:
                try:
                    await self.process_search(search)
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Erreur traitement recherche {search['id']}: {e}")

            await self.storage.clean_old_cache(
                self.config.get('cache_expiry_hours', 24)
            )

            self.stats['searches_run'] += len(active_searches)
            logger.info("Cycle de scraping terminé")

        except Exception as e:
            logger.error(f"Erreur boucle scraping: {e}")

    @scraping_loop.before_loop
    async def before_scraping_loop(self):
        """Attend que le bot soit prêt"""
        await self.wait_until_ready()

    async def process_search(self, search: Dict):
        """Traite une recherche individuelle"""
        logger.debug(f"Traitement recherche #{search['id']}: {search.get('keyword')}")

        criteria = {
            'keyword': search.get('keyword'),
            'min_price': search.get('min_price'),
            'max_price': search.get('max_price'),
            'size': search.get('size'),
            'brand': search.get('brand'),
            'condition': search.get('condition'),
            'location': search.get('location'),
            'search_id': search['id']
        }

        results = await self.scraper.search(criteria, limit=20)

        if not results:
            logger.debug(f"Aucun résultat pour recherche #{search['id']}")
            return

        # Filtrer nouveaux items
        new_items = []
        for item in results:
            if not await self.storage.is_result_cached(item['id']):
                new_items.append(item)
                await self.storage.add_to_cache(item['id'], time.time())

        logger.info(f"Recherche #{search['id']}: {len(new_items)} nouveaux articles")

        for item in new_items:
            await self.send_notification(search, item)
            self.stats['items_found'] += 1

    async def send_notification(self, search: Dict, item: Dict):
        """Envoie une notification pour un nouvel article"""
        try:
            embed = create_item_embed(item, self.lang)
            user = await self.fetch_user(search['user_id'])

            if search.get('dm_notifications', False) and user:
                try:
                    await user.send(embed=embed)
                    self.stats['notifications_sent'] += 1
                except discord.Forbidden:
                    logger.warning(f"Impossible d'envoyer DM à {user.name}")

            channel_id = search.get('guild_channel_id') or self.config.get('notification_channel_id')
            if channel_id:
                try:
                    channel = self.get_channel(int(channel_id))
                    if channel:
                        await channel.send(
                            content=f"<@{search['user_id']}>",
                            embed=embed
                        )
                        self.stats['notifications_sent'] += 1
                except Exception as e:
                    logger.error(f"Erreur envoi notification salon: {e}")

        except Exception as e:
            logger.error(f"Erreur envoi notification: {e}")

    async def run_demo(self):
        """Exécute le mode démo"""
        logger.info("Mode démo: chargement de demo_results.json")

        try:
            import json
            with open('demo_results.json', 'r', encoding='utf-8') as f:
                demo_data = json.load(f)

            await asyncio.sleep(3)

            app_info = await self.application_info()
            owner = app_info.owner

            for item in demo_data.get('items', [])[:3]:
                embed = create_item_embed(item, self.lang)
                await owner.send(
                    content="**[MODE DÉMO]** Voici un exemple de notification:",
                    embed=embed
                )
                await asyncio.sleep(2)

            logger.info("Mode démo terminé - 3 notifications envoyées")

        except FileNotFoundError:
            logger.error("Fichier demo_results.json introuvable")
        except Exception as e:
            logger.error(f"Erreur mode démo: {e}")


class VintedCommands(commands.Cog):
    """Commandes du bot Vinted"""

    def __init__(self, bot: VintedBot):
        self.bot = bot
        self.storage = bot.storage
        self.scraper = bot.scraper

    @app_commands.command(name="vinted_add", description="Ajouter une recherche Vinted")
    @app_commands.describe(
        keyword="Mot-clé de recherche",
        min_price="Prix minimum",
        max_price="Prix maximum",
        size="Taille",
        brand="Marque",
        condition="État (neuf, bon, satisfaisant)",
        location="Localisation",
        dm="Recevoir les notifications en DM (true/false)"
    )
    async def vinted_add(
        self,
        interaction: discord.Interaction,
        keyword: str,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        size: Optional[str] = None,
        brand: Optional[str] = None,
        condition: Optional[str] = None,
        location: Optional[str] = None,
        dm: Optional[bool] = False
    ):
        """Ajoute une nouvelle recherche"""
        await interaction.response.defer(ephemeral=True)

        search_data = {
            'user_id': interaction.user.id,
            'guild_id': interaction.guild_id if interaction.guild else None,
            'guild_channel_id': interaction.channel_id if interaction.guild else None,
            'keyword': keyword,
            'min_price': min_price,
            'max_price': max_price,
            'size': size,
            'brand': brand,
            'condition': condition,
            'location': location,
            'dm_notifications': dm,
            'date_created': datetime.now().isoformat(),
            'last_run': None,
            'enabled': True
        }

        try:
            search = await self.storage.add_search(search_data)
            embed = create_success_embed(
                f"Recherche #{search['id']} ajoutée !\n\n{format_search_criteria(search)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Recherche ajoutée par {interaction.user.name}: {keyword}")

        except Exception as e:
            logger.error(f"Erreur ajout recherche: {e}")
            await interaction.followup.send(
                embed=create_error_embed(f"Impossible d'ajouter la recherche: {e}"),
                ephemeral=True
            )

    @app_commands.command(name="vinted_list", description="Lister vos recherches actives")
    async def vinted_list(self, interaction: discord.Interaction):
        """Liste les recherches de l'utilisateur"""
        await interaction.response.defer(ephemeral=True)

        try:
            searches = await self.storage.get_user_searches(interaction.user.id)
            embed = create_search_list_embed(searches, self.bot.lang)
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erreur liste recherches: {e}")
            await interaction.followup.send(
                embed=create_error_embed(f"Erreur: {e}"),
                ephemeral=True
            )

    @app_commands.command(name="vinted_remove", description="Supprimer une recherche")
    @app_commands.describe(search_id="ID de la recherche à supprimer")
    async def vinted_remove(self, interaction: discord.Interaction, search_id: int):
        """Supprime une recherche"""
        await interaction.response.defer(ephemeral=True)

        try:
            success = await self.storage.remove_search(search_id, interaction.user.id)

            if success:
                embed = create_success_embed(f"Recherche #{search_id} supprimée")
            else:
                embed = create_error_embed("Recherche introuvable ou vous n'en êtes pas le propriétaire")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erreur suppression recherche: {e}")
            await interaction.followup.send(
                embed=create_error_embed(f"Erreur: {e}"),
                ephemeral=True
            )

    @app_commands.command(name="vinted_test", description="Tester une recherche")
    @app_commands.describe(search_id="ID de la recherche à tester")
    async def vinted_test(self, interaction: discord.Interaction, search_id: int):
        """Teste une recherche et affiche 3 résultats"""
        await interaction.response.defer(ephemeral=True)

        try:
            search = await self.storage.get_search_by_id(search_id)

            if not search or search['user_id'] != interaction.user.id:
                await interaction.followup.send(
                    embed=create_error_embed("Recherche introuvable"),
                    ephemeral=True
                )
                return

            criteria = {
                'keyword': search.get('keyword'),
                'min_price': search.get('min_price'),
                'max_price': search.get('max_price'),
                'size': search.get('size'),
                'brand': search.get('brand'),
                'condition': search.get('condition'),
                'search_id': search['id']
            }

            results = await self.scraper.test_search(criteria)

            if not results:
                await interaction.followup.send(
                    embed=create_error_embed("Aucun résultat trouvé"),
                    ephemeral=True
                )
                return

            await interaction.followup.send(
                content=f"**Résultats de test pour recherche #{search_id}:**",
                ephemeral=True
            )

            for item in results[:3]:
                embed = create_item_embed(item, self.bot.lang)
                await interaction.followup.send(embed=embed, ephemeral=True)
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Erreur test recherche: {e}")
            await interaction.followup.send(
                embed=create_error_embed(f"Erreur: {e}"),
                ephemeral=True
            )

    @app_commands.command(name="vinted_stats", description="Afficher les statistiques du bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def vinted_stats(self, interaction: discord.Interaction):
        """Affiche les statistiques (admin seulement)"""
        await interaction.response.defer(ephemeral=True)

        try:
            searches = await self.storage.load_searches()
            active_searches = [s for s in searches if s.get('enabled', True)]

            embed = discord.Embed(
                title="📊 Statistiques Vinted Bot",
                color=discord.Color.blue()
            )

            embed.add_field(name="Recherches actives", value=str(len(active_searches)), inline=True)
            embed.add_field(name="Recherches totales", value=str(len(searches)), inline=True)
            embed.add_field(name="Cycles effectués", value=str(self.bot.stats['searches_run']), inline=True)
            embed.add_field(name="Articles trouvés", value=str(self.bot.stats['items_found']), inline=True)
            embed.add_field(name="Notifications envoyées", value=str(self.bot.stats['notifications_sent']), inline=True)
            embed.add_field(name="Intervalle scraping", value=f"{self.bot.config.get('scraping_interval', 90)}s", inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erreur stats: {e}")
            await interaction.followup.send(
                embed=create_error_embed(f"Erreur: {e}"),
                ephemeral=True
            )

    @app_commands.command(name="vinted_set_channel", description="Définir le salon de notifications")
    @app_commands.describe(channel="Salon pour les notifications")
    @app_commands.checks.has_permissions(administrator=True)
    async def vinted_set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Définit le salon de notifications global (admin)"""
        await interaction.response.defer(ephemeral=True)

        try:
            config = await self.storage.load_config()
            config['notification_channel_id'] = channel.id
            await self.storage.save_config(config)
            self.bot.config['notification_channel_id'] = channel.id

            embed = create_success_embed(f"Salon de notifications défini: {channel.mention}")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erreur set_channel: {e}")
            await interaction.followup.send(
                embed=create_error_embed(f"Erreur: {e}"),
                ephemeral=True
            )

    @app_commands.command(name="vinted_set_interval", description="Définir l'intervalle de scraping")
    @app_commands.describe(seconds="Intervalle en secondes (minimum 30)")
    @app_commands.checks.has_permissions(administrator=True)
    async def vinted_set_interval(self, interaction: discord.Interaction, seconds: int):
        """Définit l'intervalle de scraping (admin)"""
        await interaction.response.defer(ephemeral=True)

        if seconds < 30:
            await interaction.followup.send(
                embed=create_error_embed("L'intervalle minimum est de 30 secondes"),
                ephemeral=True
            )
            return

        try:
            config = await self.storage.load_config()
            config['scraping_interval'] = seconds
            await self.storage.save_config(config)
            self.bot.config['scraping_interval'] = seconds

            self.bot.scraping_loop.change_interval(seconds=seconds)

            embed = create_success_embed(f"Intervalle de scraping défini à {seconds}s")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Erreur set_interval: {e}")
            await interaction.followup.send(
                embed=create_error_embed(f"Erreur: {e}"),
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(VintedCommands(bot))
