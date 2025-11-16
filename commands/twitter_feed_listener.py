import os
import discord
from discord.ext import commands, tasks
import tweepy
import json

# ================== CONFIG depuis l'environnement ==================
BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")
TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME")
DISCORD_CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "1439549538556973106"))
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "10"))
POSTED_TWEETS_FILE = "posted_tweet_ids.json"  # fichier pour stocker les tweets déjà postés
# ==================================================================

class TwitterFeedListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = tweepy.Client(bearer_token=BEARER_TOKEN)
        self.posted_tweet_ids = self.load_posted_tweets()
        self.check_tweets.start()

    def cog_unload(self):
        self.check_tweets.cancel()

    def load_posted_tweets(self):
        if os.path.exists(POSTED_TWEETS_FILE):
            try:
                with open(POSTED_TWEETS_FILE, "r") as f:
                    return set(json.load(f))
            except Exception as e:
                print(f"[TwitterFeedListener] Erreur lors du chargement des tweets : {e}")
        return set()

    def save_posted_tweets(self):
        try:
            with open(POSTED_TWEETS_FILE, "w") as f:
                json.dump(list(self.posted_tweet_ids), f)
        except Exception as e:
            print(f"[TwitterFeedListener] Erreur lors de la sauvegarde des tweets : {e}")

    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_tweets(self):
        try:
            # Récupère l'ID numérique du compte
            user = self.client.get_user(username=TWITTER_USERNAME)
            if not user or not user.data:
                return
            user_id = user.data.id

            # Récupère les 5 derniers tweets originaux (exclude replies & retweets)
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=5,
                tweet_fields=["created_at", "entities"],
                exclude=["replies", "retweets"]
            )
            if not tweets.data:
                return

            channel = self.bot.get_channel(DISCORD_CHANNEL_ID)
            for tweet in reversed(tweets.data):  # du plus ancien au plus récent
                if tweet.id not in self.posted_tweet_ids:
                    # Création de l'embed
                    embed = discord.Embed(
                        description=tweet.text,
                        color=discord.Color.blue(),
                        timestamp=tweet.created_at
                    )
                    embed.set_author(
                        name=f"Twitter - @{TWITTER_USERNAME}",
                        url=f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet.id}"
                    )

                    # Si le tweet contient des liens médias
                    media_urls = []
                    if tweet.entities and "urls" in tweet.entities:
                        media_urls = [url["expanded_url"] for url in tweet.entities["urls"]]
                    if media_urls:
                        embed.add_field(name="Lien", value="\n".join(media_urls), inline=False)

                    await channel.send(embed=embed)
                    self.posted_tweet_ids.add(tweet.id)
                    self.save_posted_tweets()

        except Exception as e:
            print(f"[TwitterFeedListener] Erreur lors de la récupération des tweets : {e}")

    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TwitterFeedListener(bot))
