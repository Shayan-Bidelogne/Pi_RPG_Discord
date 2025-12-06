import os
import discord
from discord.ext import commands, tasks
import tweepy
import json
import asyncio
import time

# ================== CONFIG ==================
BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")
TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME")  # ex: "pirpg"
DISCORD_CHANNEL_TWITTER_ID = int(os.environ.get("DISCORD_CHANNEL_TWITTER_ID", "1439549538556973106"))
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "10"))
POSTED_TWEETS_FILE = "posted_tweet_ids.json"
# ============================================

class TwitterFeedListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = tweepy.Client(bearer_token=BEARER_TOKEN)
        self.user_id = None
        self.posted_tweet_ids = self.load_posted_tweets()
        self.last_tweet = None
        self.last_includes = None
        self.check_tweets.start()

    def cog_unload(self):
        self.check_tweets.cancel()

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

    def get_last_tweet_full(self):
        return self.last_tweet, self.last_includes

    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_tweets(self):
        try:
            if self.user_id is None:
                user = self.client.get_user(username=TWITTER_USERNAME)
                if not user or not user.data:
                    return
                self.user_id = user.data.id

            tweets = self.client.get_users_tweets(
                id=self.user_id,
                max_results=5,
                tweet_fields=["created_at", "entities", "attachments"],
                expansions=["attachments.media_keys"],
                media_fields=["url", "preview_image_url", "type", "variants"],
                exclude=["replies", "retweets"]
            )

            if not tweets.data:
                return

            tweet = tweets.data[0]

            if tweet.id not in self.posted_tweet_ids:
                channel = self.bot.get_channel(DISCORD_CHANNEL_TWITTER_ID)

                embed = discord.Embed(
                    description=tweet.text,
                    color=discord.Color.blue(),
                    timestamp=tweet.created_at
                )
                embed.set_author(
                    name=f"Twitter - @{TWITTER_USERNAME}",
                    url=f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet.id}"
                )

                urls = []
                if tweet.entities and "urls" in tweet.entities:
                    urls = [u["expanded_url"] for u in tweet.entities["urls"]]
                if urls:
                    embed.add_field(name="Lien", value="\n".join(urls), inline=False)

                await channel.send(embed=embed)

                media_dict = {m["media_key"]: m for m in tweets.includes.get("media", [])} if tweets.includes else {}
                if tweet.attachments and "media_keys" in tweet.attachments:
                    for key in tweet.attachments["media_keys"]:
                        media = media_dict.get(key)
                        if media:
                            url_to_show = media.get("url") or media.get("preview_image_url")
                            if url_to_show:
                                await channel.send(embed=discord.Embed().set_image(url=url_to_show))

                self.posted_tweet_ids.add(tweet.id)
                self.save_posted_tweets()
                self.last_tweet = tweet
                self.last_includes = tweets.includes if tweets.includes else {}

        except tweepy.TooManyRequests as e:
            reset_timestamp = e.response.headers.get("x-rate-limit-reset")
            wait_time = int(reset_timestamp) - int(time.time()) if reset_timestamp else 60
            wait_time = max(wait_time, 1)
            print(f"[TwitterFeedListener] Rate limit atteint. Pause {wait_time}s")
            await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"[TwitterFeedListener] Erreur récupération tweets : {e}")

    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(TwitterFeedListener(bot))
