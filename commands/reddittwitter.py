import os
import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncpraw
import aiohttp
import tempfile

# ================== Config ==================
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "1401352070505824306"))

# Subreddits disponibles
SUBREDDITS = ["test", "mySubreddit1", "mySubreddit2"]

# ================== Init Reddit ==================
reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
    user_agent=f"discord:mybot:v1.0 (by u/{REDDIT_USERNAME})",
)

# ================== Cog ==================
class RedditPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def clean_label(self, text: str) -> str:
        """Nettoie et tronque à 100 caractères"""
        clean = text.replace("\n", " ").strip()
        return clean[:97] + "..." if len(clean) > 100 else clean

    @app_commands.command(name="reddit", description="Poster un tweet depuis la bibliothèque sur Reddit")
    async def reddit_from_library(self, interaction: discord.Interaction):
        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not channel:
            await interaction.response.send_message("❌ Library channel not found.", ephemeral=True)
            return

        # Récupère les 50 derniers messages
        messages = [msg async for msg in channel.history(limit=50)]
        if not messages:
            await interaction.response.send_message("❌ No tweets in the library.", ephemeral=True)
            return

        # helper: crée un label sûr (1-100 chars) et explicite
        def make_label(msg, idx):
            preview = (msg.content or "").replace("\n", " ").strip()
            if preview:
                preview = self.clean_label(preview)
            elif msg.attachments:
                att = msg.attachments[0]
                name = getattr(att, "filename", None) or att.url or "Attachment"
                preview = name.replace("\n", " ").strip()
            else:
                preview = "[No text]"
            label = f"#{idx+1} — {preview}"
            return label[:100] or "[No text]"

        # ---------- Menu de sélection du tweet ----------
        class TweetSelect(ui.Select):
            def __init__(self, messages):
                options = [
                    discord.SelectOption(label=make_label(msg, i), value=str(i))
                    for i, msg in enumerate(messages[:25])
                ]
                super().__init__(placeholder="Choose a tweet...", options=options, min_values=1, max_values=1)
                self.messages = messages

            async def callback(self, interaction2: discord.Interaction):
                idx = int(self.values[0])
                msg = self.messages[idx]
                # store selected tweet on the view for next step
                view = SubredditView(msg)
                await interaction2.response.send_message("Choose a subreddit:", view=view, ephemeral=True)

        class TweetView(ui.View):
            def __init__(self, messages):
                super().__init__(timeout=120)
                self.add_item(TweetSelect(messages))

        # ---------- Menu subreddit (view + select) ----------
        class SubredditSelect(ui.Select):
            def __init__(self, msg):
                options = [discord.SelectOption(label=sub, value=sub) for sub in SUBREDDITS[:25]]
                super().__init__(placeholder="Choose a subreddit...", options=options, min_values=1, max_values=1)
                self.msg = msg

            async def callback(self, interaction3: discord.Interaction):
                subreddit_name = self.values[0]
                msg = self.msg

                # Gestion média si attachments
                media_info = None
                if msg.attachments:
                    att = msg.attachments[0]
                    content_type = getattr(att, "content_type", "") or ""
                    media_info = {
                        "url": att.url,
                        "type": "photo" if content_type.startswith("image") else "video"
                    }

                await interaction3.response.defer(ephemeral=True)
                try:
                    subreddit_obj = await reddit.subreddit(subreddit_name, fetch=True)

                    if media_info:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(media_info["url"]) as resp:
                                if resp.status == 200:
                                    suffix = ".mp4" if media_info["type"] == "video" else None
                                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                                    tmp_file.write(await resp.read())
                                    tmp_file.close()
                                    if media_info["type"] == "photo":
                                        submission = await subreddit_obj.submit_image(
                                            title=(msg.content or "")[:300],
                                            image_path=tmp_file.name
                                        )
                                    else:
                                        submission = await subreddit_obj.submit_video(
                                            title=(msg.content or "")[:300],
                                            video_path=tmp_file.name
                                        )
                                    try:
                                        os.unlink(tmp_file.name)
                                    except Exception:
                                        pass
                                else:
                                    await interaction3.followup.send("❌ Failed to download attachment.", ephemeral=True)
                                    return
                    else:
                        submission = await subreddit_obj.submit(title=(msg.content or "")[:300], selftext=(msg.content or ""))

                    await interaction3.followup.send(f"✅ Reddit post published: https://reddit.com{submission.permalink}", ephemeral=True)
                except Exception as e:
                    await interaction3.followup.send(f"❌ Reddit error: {e}", ephemeral=True)

        class SubredditView(ui.View):
            def __init__(self, msg):
                super().__init__(timeout=120)
                self.add_item(SubredditSelect(msg))

        await interaction.response.send_message("📚 Select a tweet from the library:", view=TweetView(messages), ephemeral=True)


async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
