import os
import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncpraw
import aiohttp
import tempfile
import re

from commands.twitter_feed import TwitterFeedListener  # Import Cog Twitter

# ================== Config Reddit ==================
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
DISCORD_CHANNEL_CONFIRM_ID = int(os.environ.get("DISCORD_CHANNEL_CONFIRM_ID", "1401352070505824306"))

# ================== Init Reddit ==================
reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
    user_agent=f"discord:mybot:v1.0 (by u/{REDDIT_USERNAME})",
)

# ================== Cog Reddit ==================
class RedditPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reddit", description="Poster le dernier tweet sur Reddit avec confirmation")
    async def reddit_from_tweet(self, interaction: discord.Interaction):
        listener: TwitterFeedListener = self.bot.get_cog("TwitterFeedListener")
        tweet, includes = listener.get_last_tweet_full()

        if not tweet:
            await interaction.response.send_message("❌ Aucun tweet disponible pour poster.", ephemeral=True)
            return

        # Construire media_dict depuis includes
        media_dict = {}
        if includes:
            media_list = includes.get("media", [])
            for m in media_list:
                media_dict[m["media_key"]] = m

        media_info = None
        if tweet.attachments and "media_keys" in tweet.attachments:
            for key in tweet.attachments["media_keys"]:
                media_info = media_dict.get(key)
                break

        # Embed Discord
        embed = discord.Embed(
            description=tweet.text,
            color=discord.Color.orange(),
            timestamp=tweet.created_at
        )
        embed.set_author(
            name=f"Twitter - @{os.environ.get('TWITTER_USERNAME')}",
            url=f"https://twitter.com/{os.environ.get('TWITTER_USERNAME')}/status/{tweet.id}"
        )
        if media_info:
            url_preview = media_info.get("url") or media_info.get("preview_image_url")
            if url_preview:
                embed.set_image(url=url_preview)

        # ---------- View / Menu Select ----------
        class SubredditSelect(ui.View):
            def __init__(self):
                super().__init__(timeout=120)
                self.add_item(
                    ui.Select(
                        placeholder="Choisis le subreddit...",
                        options=[
                            discord.SelectOption(label="r/test", value="test"),
                            discord.SelectOption(label="r/mySubreddit1", value="mySubreddit1"),
                            discord.SelectOption(label="r/mySubreddit2", value="mySubreddit2"),
                        ],
                        custom_id="subreddit_select"
                    )
                )
                self.add_item_callback(self.children[0])

            def add_item_callback(self, select):
                select.callback = self.select_callback

            async def select_callback(self, interaction2: discord.Interaction):
                values = interaction2.data.get("values", [])
                subreddit_name = values[0] if values else None

                if not subreddit_name:
                    await interaction2.response.send_message("❌ Pas de subreddit sélectionné.", ephemeral=True)
                    return

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
                                v["url"] for v in variants if "bitrate" in v and v["content_type"]=="video/mp4"
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


async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
