import os
import json
import tempfile
import aiohttp

import discord
from discord import app_commands
from discord.ext import commands, tasks
import tweepy

# ================== Config ==================
BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")
TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME")  # ex: "pirpg"
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "1439549538556973106"))
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "10"))
POSTED_TWEETS_FILE = "posted_tweet_ids.json"

# ================== Cog ==================
class TwitterFeedListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = tweepy.Client(bearer_token=BEARER_TOKEN)
        self.user_id = None
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
                print(f"[TwitterFeedListener] Error loading posted tweets: {e}")
        return set()

    def save_posted_tweets(self):
        try:
            with open(POSTED_TWEETS_FILE, "w") as f:
                json.dump(list(self.posted_tweet_ids), f)
        except Exception as e:
            print(f"[TwitterFeedListener] Error saving posted tweets: {e}")

    async def fetch_and_post_tweets(self):
        try:
            # ensure user id
            if self.user_id is None:
                user = self.client.get_user(username=TWITTER_USERNAME)
                if not user or not getattr(user, "data", None):
                    print("[TwitterFeedListener] Could not fetch twitter user.")
                    return
                self.user_id = user.data.id

            # get recent tweets with media expansions
            tweets = self.client.get_users_tweets(
                id=self.user_id,
                max_results=5,
                tweet_fields=["created_at", "entities", "attachments"],
                expansions=["attachments.media_keys"],
                media_fields=["url", "preview_image_url", "type", "variants"],
                exclude=["replies", "retweets"],
            )

            if not getattr(tweets, "data", None):
                return

            channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
            if not channel:
                print(f"[TwitterFeedListener] Channel {DISCORD_CHANNEL_LIBRARY_ID} not found.")
                return

            media_list = tweets.includes.get("media", []) if getattr(tweets, "includes", None) else []
            # build media dict keyed by media_key
            media_dict = {}
            for m in media_list:
                # tweepy objects may be dict-like or objects; handle both
                try:
                    key = m.get("media_key") if isinstance(m, dict) else getattr(m, "media_key", None)
                except Exception:
                    key = None
                if key:
                    media_dict[key] = m

            for tweet in tweets.data:
                tid = getattr(tweet, "id", None)
                if not tid or tid in self.posted_tweet_ids:
                    continue

                embed = discord.Embed(
                    description=getattr(tweet, "text", "") or "",
                    color=discord.Color.orange(),
                    timestamp=getattr(tweet, "created_at", None)
                )
                embed.set_author(
                    name=f"Twitter - @{TWITTER_USERNAME}",
                    url=f"https://twitter.com/{TWITTER_USERNAME}/status/{tid}"
                )

                # default values
                video_download_url = None
                image_url = None

                attachments = getattr(tweet, "attachments", None) or {}
                media_keys = attachments.get("media_keys", []) if isinstance(attachments, dict) else getattr(attachments, "media_keys", []) or []

                for key in media_keys:
                    m = media_dict.get(key)
                    if not m:
                        continue
                    m_type = (m.get("type") if isinstance(m, dict) else getattr(m, "type", None)) or ""

                    if m_type == "photo":
                        image_url = (m.get("url") if isinstance(m, dict) else getattr(m, "url", None)) or (m.get("preview_image_url") if isinstance(m, dict) else getattr(m, "preview_image_url", None))
                        if image_url:
                            embed.set_image(url=image_url)
                            # for photos we can stop scanning media keys
                            break

                    elif m_type in ("video", "animated_gif"):
                        # pick best mp4 variant if present
                        variants = (m.get("variants") if isinstance(m, dict) else getattr(m, "variants", None)) or []
                        mp4_variants = []
                        for v in variants:
                            v_url = v.get("url") if isinstance(v, dict) else getattr(v, "url", None)
                            v_ct = v.get("content_type") if isinstance(v, dict) else getattr(v, "content_type", None)
                            v_br = v.get("bit_rate") if isinstance(v, dict) else getattr(v, "bit_rate", None)
                            if v_url and v_ct and v_ct.startswith("video/mp4"):
                                try:
                                    bitrate = int(v_br) if v_br is not None else 0
                                except Exception:
                                    bitrate = 0
                                mp4_variants.append((bitrate, v_url))
                        if mp4_variants:
                            mp4_variants.sort(reverse=True)
                            video_download_url = mp4_variants[0][1]
                        else:
                            # no direct mp4 variant — try preview_image_url as thumbnail only
                            image_url = (m.get("preview_image_url") if isinstance(m, dict) else getattr(m, "preview_image_url", None))
                            if image_url:
                                embed.set_image(url=image_url)
                        # prefer first video found
                        if video_download_url or image_url:
                            break

                    else:
                        # unknown media: try to use url/preview as image
                        url = (m.get("url") if isinstance(m, dict) else getattr(m, "url", None)) or (m.get("preview_image_url") if isinstance(m, dict) else getattr(m, "preview_image_url", None))
                        if url and not image_url:
                            image_url = url
                            embed.set_image(url=image_url)

                # store tweet id in footer for later grouping
                embed.set_footer(text=f"Tweet ID: {tid}")

                # Send: if we have a downloadable mp4 variant, download and attach the file in the SAME message.
                if video_download_url:
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(video_download_url, timeout=60) as resp:
                                if resp.status == 200:
                                    data = await resp.read()
                                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                                    try:
                                        # name file with tweet id to help grouping later
                                        tmp.write(data)
                                        tmp.close()
                                        discord_file = discord.File(tmp.name, filename=f"{tid}.mp4")
                                        await channel.send(embed=embed, file=discord_file)
                                    finally:
                                        try:
                                            os.unlink(tmp.name)
                                        except Exception:
                                            pass
                                else:
                                    # download failed -> send embed (thumbnail) only
                                    await channel.send(embed=embed)
                    except Exception as e:
                        print(f"[TwitterFeedListener] Error downloading/video attaching {video_download_url}: {e}")
                        await channel.send(embed=embed)
                else:
                    # no downloadable mp4 variant — send embed (image if set) only
                    await channel.send(embed=embed)

                self.posted_tweet_ids.add(tid)

            self.save_posted_tweets()

        except Exception as e:
            print(f"[TwitterFeedListener] Error fetching tweets: {e}")

    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_tweets(self):
        await self.fetch_and_post_tweets()

    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="twitterfeed", description="Force import latest tweets into the library now")
    async def twitterfeed(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.fetch_and_post_tweets()
        await interaction.followup.send("✅ Twitter feed import finished.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(TwitterFeedListener(bot))
