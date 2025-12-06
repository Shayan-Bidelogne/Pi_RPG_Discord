import os
import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import tweepy
import json
import asyncio
import time
import asyncpraw
import aiohttp
import tempfile
import re

# ================== CONFIG depuis l'environnement ==================
BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")
TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME")  # ex: "pirpg"
DISCORD_CHANNEL_TWITTER_ID = int(os.environ.get("DISCORD_CHANNEL_TWITTER_ID", "1439549538556973106"))  # #AAA
DISCORD_CHANNEL_CONFIRM_ID = int(os.environ.get("DISCORD_CHANNEL_CONFIRM_ID", "1401352070505824306"))  # #BBB
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "10"))
POSTED_TWEETS_FILE = "posted_tweet_ids.json"

# Reddit env
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
# ==================================================================

# Initialisation Reddit
reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
    user_agent=f"discord:mybot:v1.0 (by u/{REDDIT_USERNAME})",
)

# ------------------- Cog Twitter -------------------
class TwitterFeedListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = tweepy.Client(bearer_token=BEARER_TOKEN)
        self.user_id = None
        self.posted_tweet_ids = self.load_posted_tweets()
        self.last_tweet = None
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
        return self.last_tweet

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


# ------------------- Cog Reddit -------------------
# ------------------- Cog Reddit corrigé -------------------
class RedditPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reddit", description="Poster le dernier tweet sur Reddit avec confirmation")
    async def reddit_from_tweet(self, interaction: discord.Interaction):
        listener: TwitterFeedListener = self.bot.get_cog("TwitterFeedListener")
        tweet = listener.get_last_tweet_full()

        if not tweet:
            await interaction.response.send_message("❌ Aucun tweet disponible pour poster.", ephemeral=True)
            return

        # Récupérer les médias depuis l'objet tweets complet
        tweets_obj = listener.client.get_users_tweets(
            id=listener.user_id,
            max_results=5,
            tweet_fields=["attachments"],
            expansions=["attachments.media_keys"],
            media_fields=["url", "preview_image_url", "type", "variants"]
        )
        media_dict = {}
        if hasattr(tweets_obj, "includes") and tweets_obj.includes:
            media_list = tweets_obj.includes.get("media", [])
            for m in media_list:
                media_dict[m["media_key"]] = m

        media_info = None
        if tweet.attachments and "media_keys" in tweet.attachments:
            for key in tweet.attachments["media_keys"]:
                media_info = media_dict.get(key)
                break  # prendre seulement le premier média pour Reddit

        # Création de l'embed de confirmation
        embed = discord.Embed(
            description=tweet.text,
            color=discord.Color.orange(),
            timestamp=tweet.created_at
        )
        embed.set_author(
            name=f"Twitter - @{TWITTER_USERNAME}",
            url=f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet.id}"
        )
        if media_info:
            url_preview = media_info.get("url") or media_info.get("preview_image_url")
            if url_preview:
                embed.set_image(url=url_preview)

        # ---------- Menu select pour subreddit ----------
        class SubredditSelect(ui.View):
            def __init__(self):
                super().__init__(timeout=120)

            @ui.select(
                placeholder="Choisis le subreddit...",
                options=[
                    discord.SelectOption(label="r/test", value="test"),
                    discord.SelectOption(label="r/mySubreddit1", value="mySubreddit1"),
                    discord.SelectOption(label="r/mySubreddit2", value="mySubreddit2"),
                ]
            )
            async def select_callback(self, select: ui.Select, interaction2: discord.Interaction):
                subreddit_name = select.values[0]
                await interaction2.response.defer()
                try:
                    subreddit_obj = await reddit.subreddit(subreddit_name, fetch=True)
                    # Gestion média
                    if media_info:
                        if media_info["type"] == "photo":
                            async with aiohttp.ClientSession() as session:
                                async with session.get(media_info["url"]) as resp:
                                    if resp.status == 200:
                                        tmp_file = tempfile.NamedTemporaryFile(delete=False)
                                        tmp_file.write(await resp.read())
                                        tmp_file.close()
                                        submission = await subreddit_obj.submit_image(
                                            title=tweet.text[:300], image_path=tmp_file.name
                                        )
                                        os.unlink(tmp_file.name)
                        elif media_info["type"] in ["video", "animated_gif"]:
                            variants = media_info.get("variants", [])
                            mp4_urls = [
                                v["url"] for v in variants if "bitrate" in v and v["content_type"] == "video/mp4"
                            ]
                            if mp4_urls:
                                best_url = sorted(
                                    mp4_urls,
                                    key=lambda x: int(re.search(r"(\d+)", x).group(1) if re.search(r"(\d+)", x) else 0),
                                    reverse=True
                                )[0]
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(best_url) as resp:
                                        if resp.status == 200:
                                            tmp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                                            tmp_file.write(await resp.read())
                                            tmp_file.close()
                                            submission = await subreddit_obj.submit_video(
                                                title=tweet.text[:300], video_path=tmp_file.name
                                            )
                                            os.unlink(tmp_file.name)
                    else:
                        submission = await subreddit_obj.submit(title=tweet.text[:300], selftext=tweet.text)

                    await interaction2.followup.send(
                        f"✅ Post Reddit publié : https://reddit.com{submission.permalink}", ephemeral=True
                    )
                except Exception as e:
                    await interaction2.followup.send(f"❌ Erreur Reddit : {e}", ephemeral=True)

        channel = self.bot.get_channel(DISCORD_CHANNEL_CONFIRM_ID)
        await channel.send(embed=embed, view=SubredditSelect())
        await interaction.response.send_message(
            f"✅ Tweet préparé pour Reddit dans <#{DISCORD_CHANNEL_CONFIRM_ID}>", ephemeral=True
        )
