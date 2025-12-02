# 🛍️ Bot Discord Vinted

Bot Discord complet pour surveiller Vinted et recevoir des notifications automatiques sur les nouvelles annonces correspondant à vos critères de recherche.

## ⚠️ Avertissements Importants

### Sécurité
- **Le token Discord est stocké en clair dans `config.json`**. Ne partagez JAMAIS ce fichier.
- En production, utilisez des variables d'environnement ou un gestionnaire de secrets.
- Activez l'authentification à deux facteurs sur votre compte Discord.

### Légalité & Éthique
- Ce bot effectue du scraping sur Vinted, ce qui peut violer leurs conditions d'utilisation.
- Vinted peut bloquer votre IP ou implémenter des CAPTCHAs.
- Utilisez ce bot à vos risques et périls, uniquement à des fins éducatives.
- Respectez `robots.txt` de Vinted : https://www.vinted.fr/robots.txt
- Le scraping intensif peut surcharger les serveurs de Vinted.

### Limitations Techniques
- La structure HTML de Vinted change régulièrement, ce qui peut casser le scraper.
- Les CAPTCHAs ne sont PAS contournés (et ne doivent pas l'être).
- Le bot inclut des mécanismes de throttling mais peut quand même être bloqué.

## 📋 Prérequis

- Python 3.10 ou supérieur
- Un compte Discord avec un bot créé sur https://discord.com/developers
- Connexion Internet stable

## 🚀 Installation

### 1. Cloner ou télécharger le projet
```bash
git clone <votre-repo>
cd vinted-discord-bot
