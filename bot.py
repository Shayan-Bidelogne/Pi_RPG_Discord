import os
import json
from datetime import datetime

import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ✅ Charger .env uniquement en local (Railway injecte déjà les variables)
if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ .env chargé (en local)")

# ✅ Récupération des variables d'environnement
TOKEN = os.getenv("TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

# ✅ Vérification du token Discord
if not TOKEN:
    raise ValueError(
        "❌ Le token Discord n'a pas été défini.\n"
        "En local : vérifie ton fichier .env\n"
        "Sur Railway : ajoute la variable TOKEN dans 'Variables'"
    )

# ✅ Intents nécessaires pour les événements Discord
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
bot = commands.Bot(command_prefix="!", intents=intents)


# ✅ Fonction pour charger dynamiquement les extensions dans /commands
async def load_extensions():
    if not os.path.exists("./commands"):
        print("⚠️ Aucun dossier commands trouvé")
        return
    
    for filename in os.listdir("./commands"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"commands.{filename[:-3]}")
                print(f"✅ Extension chargée : {filename}")
            except Exception as e:
                print(f"❌ Erreur lors du chargement de {filename}: {e}")

# ✅ Événement quand le bot est prêt
@bot.event
async def on_ready():
    print(f"🤖 {bot.user} est en ligne !")
    try:
        await load_extensions()
        print("✅ Toutes les extensions ont été chargées.")

        synced = await bot.tree.sync()
        print(f"🔄 {len(synced)} commandes slash synchronisées.")

        await bot.load_extension("commands.autoresponseticket")
        print("✅ TicketListener chargé.")

    except Exception as e:
        print(f"⚠️ Erreur lors de l'initialisation : {e}")

# ✅ Lancer le bot
bot.run(TOKEN)
