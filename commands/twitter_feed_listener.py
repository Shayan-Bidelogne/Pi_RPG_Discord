import os
import discord
from discord.ext import commands, tasks
import tweepy
import json
import asyncio
import time

# ================== CONFIG depuis l'environnement ==================
BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")
TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME")  # ex: "pirpg"
DISCORD_CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "1439549538556973106"))
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "15"))
POSTED_TWEETS_FILE = "posted_tweet_ids.json"
# ==================================================================

class TwitterFeedListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = tweepy.Client(bearer_token=BEARER_TOKEN)
        self.user_id = None  # Stocke l'ID Twitter pour limiter les appels
        self.posted_tweet_ids = self.load_posted_tweets()
        self.check_tweets.start()

    def cog_unload(self):
        self.check_tweets.cancel()

    # ---------- Gestion persistance ----------
    def load_posted_tweets(self):
        if os.path.exists(POSTED_TWEETS_FILE):
            try:
                with open(POSTED_TWEETS_FILE, "r") as f:
                    return set(json.load(f))
            except Exception as e:
                print(f"[TwitterFeedListener] Erreur chargement tweets : {e}")
        return set()

    def save_posted_tweets(self):
        try:
            with open(POSTED_TWEETS_FILE, "w") as f:
                json.dump(list(self.posted_tweet_ids), f)
        except Exception as e:
            print(f"[TwitterFeedListener] Erreur sauvegarde tweets : {e}")

    # ---------- Boucle principale ----------
    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_tweets(self):
        try:
            # Récupère l'ID utilisateur une seule fois
            if self.user_id is None:
                user = self.client.get_user(username=TWITTER_USERNAME)
                if not user or not user.data:
                    return
                self.user_id = user.data.id

            # Récupère le dernier tweet original avec médias
            tweets = self.client.get_users_tweets(
                id=self.user_id,
                max_results=5,
                tweet_fields=["created_at", "entities", "attachments"],
                expansions=["attachments.media_keys"],
                media_fields=["url", "preview_image_url", "type"],
                exclude=["replies", "retweets"]
            )

            if not tweets.data:
                return

            tweet = tweets.data[0]

            # Vérifie si le tweet est déjà posté
            if tweet.id not in self.posted_tweet_ids:
                channel = self.bot.get_channel(DISCORD_CHANNEL_ID)

                # Création du premier embed avec texte
                embed = discord.Embed(
                    description=tweet.text,
                    color=discord.Color.blue(),
                    timestamp=tweet.created_at
                )
                embed.set_author(
                    name=f"Twitter - @{TWITTER_USERNAME}",
                    url=f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet.id}"
                )

                # Liens du tweet
                urls = []
                if tweet.entities and "urls" in tweet.entities:
                    urls = [u["expanded_url"] for u in tweet.entities["urls"]]
                if urls:
                    embed.add_field(name="Lien", value="\n".join(urls), inline=False)

                await channel.send(embed=embed)

                # Ajout des médias (images ou preview vidéo)
                media_dict = {m["media_key"]: m for m in tweets.includes.get("media", [])} if tweets.includes else {}
                if tweet.attachments and "media_keys" in tweet.attachments:
                    for key in tweet.attachments["media_keys"]:
                        media = media_dict.get(key)
                        if media:
                            if media["type"] == "photo":
                                await channel.send(embed=discord.Embed().set_image(url=media["url"]))
                            elif media["type"] in ["video", "animated_gif"]:
                                if "preview_image_url" in media:
                                    await channel.send(embed=discord.Embed().set_image(url=media["preview_image_url"]))

                # Sauvegarde du tweet pour éviter duplication
                self.posted_tweet_ids.add(tweet.id)
                self.save_posted_tweets()

        except tweepy.TooManyRequests as e:
            # Calcul du temps à attendre depuis le timestamp reset
            reset_timestamp = e.response.headers.get("x-rate-limit-reset")
            if reset_timestamp:
                wait_time = int(reset_timestamp) - int(time.time())
                wait_time = max(wait_time, 1)  # au moins 1 seconde
            else:
                wait_time = 60
            print(f"[TwitterFeedListener] Rate limit atteint. Pause {wait_time}s")
            await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"[TwitterFeedListener] Erreur récupération tweets : {e}")

    # ---------- Avant la première boucle ----------
    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.bot.wait_until_ready()

# ---------- Chargement du cog ----------
async def setup(bot):
    await bot.add_cog(TwitterFeedListener(bot))
