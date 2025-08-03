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

# ✅ Planificateur de tâches (tweets programmés)
scheduler = AsyncIOScheduler()

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

# ✅ Fonction pour planifier les tweets déjà validés
async def schedule_validated_tweets():
    validated_tweet_folder = 'validated_tweets/'
    if not os.path.exists(validated_tweet_folder):
        print("ℹ️ Aucun tweet validé à reprogrammer.")
        return
    
    tweet_files = [f for f in os.listdir(validated_tweet_folder) if f.endswith('_tweet.json')]

    for tweet_file in tweet_files:
        tweet_id = tweet_file.split('_')[0]
        tweet_log_path = os.path.join(validated_tweet_folder, tweet_file)
        
        try:
            with open(tweet_log_path, 'r') as log_file:
                tweet_data = json.load(log_file)
            
            publish_time = datetime.strptime(tweet_data['publish_time'], '%Y-%m-%d %H:%M')

            def post_tweet_scheduled():
                # TODO : Implémenter la fonction de publication
                # Exemple : post_tweet(tweet_data['message'], tweet_id)
                pass

            scheduler.add_job(post_tweet_scheduled, 'date', run_date=publish_time, id=tweet_id)

            if not scheduler.running:
                scheduler.start()
            
            print(f"✅ Tweet {tweet_id} reprogrammé pour {publish_time.strftime('%Y-%m-%d %H:%M')}.")

        except Exception as e:
            print(f"⚠️ Impossible de programmer le tweet {tweet_id}: {e}")

# ✅ Événement quand le bot est prêt
@bot.event
async def on_ready():
    print(f"🤖 {bot.user} est en ligne !")
    try:
        await load_extensions()
        print("✅ Toutes les extensions ont été chargées.")

        synced = await bot.tree.sync()
        print(f"🔄 {len(synced)} commandes slash synchronisées.")

        await bot.load_extension("commands.ticket_listener")
        print("✅ TicketListener chargé.")

    except Exception as e:
        print(f"⚠️ Erreur lors de l'initialisation : {e}")

# ✅ Lancer le bot
bot.run(TOKEN)
