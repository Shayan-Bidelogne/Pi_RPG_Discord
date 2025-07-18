import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import json
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

TOKEN = os.getenv("TOKEN")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

if not TOKEN:
    raise ValueError("Le token n'a pas été défini dans le fichier .env")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Initialisation du planificateur
scheduler = AsyncIOScheduler()

# Fonction pour charger les extensions de manière asynchrone
async def load_extensions():
    for filename in os.listdir("./commands"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"commands.{filename[:-3]}")
                print(f"✅ Loaded extension: {filename}")
            except Exception as e:
                print(f"❌ Failed to load extension {filename}: {e}")

# Fonction pour planifier automatiquement les tweets validés au redémarrage
async def schedule_validated_tweets():
    validated_tweet_folder = 'validated_tweets/'
    if not os.path.exists(validated_tweet_folder):
        return
    
    # Récupère tous les fichiers de tweets validés
    tweet_files = [f for f in os.listdir(validated_tweet_folder) if f.endswith('_tweet.json')]

    for tweet_file in tweet_files:
        tweet_id = tweet_file.split('_')[0]  # ID du tweet
        tweet_log_path = os.path.join(validated_tweet_folder, tweet_file)
        
        try:
            # Lire les données du tweet
            with open(tweet_log_path, 'r') as log_file:
                tweet_data = json.load(log_file)
            
            # Convertir la date et l'heure de publication
            publish_time = datetime.strptime(tweet_data['publish_time'], '%Y-%m-%d %H:%M')

            # Fonction pour publier le tweet
            def post_tweet_scheduled():
                # Vous devrez appeler la fonction de publication ici (post_tweet)
                # Exemple : post_tweet(tweet_data['message'], tweet_id)
                pass

            # Ajouter la tâche au planificateur
            scheduler.add_job(post_tweet_scheduled, 'date', run_date=publish_time, id=tweet_id)

            # Démarrer le planificateur si ce n'est pas déjà fait
            if not scheduler.running:
                scheduler.start()
            
            print(f"✅ Tweet {tweet_id} scheduled for {publish_time.strftime('%Y-%m-%d %H:%M')}.")

        except Exception as e:
            print(f"⚠️ Failed to schedule tweet {tweet_id}: {e}")

@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    try:
        # 1. Charger les extensions d'abord
        await load_extensions()
        print("✅ All extensions loaded.")

        # 2. Ensuite synchroniser les commandes slash
        synced = await bot.tree.sync()
        print(f"🔁 Synced {len(synced)} commands")

        # 3. Planifier les tweets validés au redémarrage
        await schedule_validated_tweets()

    except Exception as e:
        print(f"⚠️ Error during setup: {e}")

# Lancer le bot
bot.run(TOKEN)
