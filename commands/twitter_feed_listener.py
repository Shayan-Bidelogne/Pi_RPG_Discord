import os
import discord
from discord.ext import commands, tasks
import tweepy

# ================== CONFIG depuis l'environnement ==================
TWITTER_API_KEY = os.environ.get("TWITTER_API_KEY")
TWITTER_API_SECRET = os.environ.get("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.environ.get("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_USERNAME = "pi.rpg"
DISCORD_CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "1439549538556973106"))  # converti en int
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "1"))  
# ==================================================================

class TwitterFeedListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Authentification OAuth1
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY, TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
        )
        self.client = tweepy.API(auth)

        self.posted_tweet_ids = set()  # Pour éviter les doublons
        self.check_tweets.start()

    def cog_unload(self):
        self.check_tweets.cancel()

    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_tweets(self):
        try:
            tweets = self.client.user_timeline(
                screen_name=TWITTER_USERNAME,
                count=5,
                tweet_mode="extended"
            )

            if not tweets:
                return

            channel = self.bot.get_channel(DISCORD_CHANNEL_ID)
            for tweet in reversed(tweets):  # du plus ancien au plus récent
                if tweet.id not in self.posted_tweet_ids:
                    embed = discord.Embed(
                        description=tweet.full_text,
                        color=discord.Color.blue(),
                        timestamp=tweet.created_at
                    )
                    embed.set_author(
                        name=f"Twitter - @{TWITTER_USERNAME}",
                        url=f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet.id}"
                    )

                    media = tweet.entities.get("media", [])
                    if media:
                        embed.set_image(url=media[0]["media_url_https"])

                    await channel.send(embed=embed)
                    self.posted_tweet_ids.add(tweet.id)

        except Exception as e:
            print(f"[TwitterFeedListener] Erreur lors de la récupération des tweets : {e}")

    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TwitterFeedListener(bot))
