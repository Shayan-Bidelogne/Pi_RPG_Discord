import os
import shutil
import json
import tempfile
import asyncio
import subprocess

import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncpraw
import aiohttp

# ================== Config ==================
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "1439549538556973106"))

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

# ================== Helpers ==================
IMAGE_CT_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None

async def download_media_to_temp(url: str, session: aiohttp.ClientSession):
    """
    Download URL, return (file_path, content_type) or (None, None) on failure.
    If content_type is a non-mp4 video and ffmpeg available, transcode to mp4.
    """
    try:
        async with session.get(url, timeout=60) as resp:
            if resp.status != 200:
                return None, None
            content_type = (resp.headers.get("Content-Type") or "").lower()
            data = await resp.read()
    except Exception:
        return None, None

    # Image
    if content_type.startswith("image") or any(url.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
        ext = IMAGE_CT_EXT.get(content_type)
        if not ext:
            # infer from URL
            for e in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                if url.lower().endswith(e):
                    ext = e
                    break
        if not ext:
            ext = ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(data)
        tmp.close()
        return tmp.name, content_type or "image/jpeg"

    # Video
    if content_type.startswith("video") or any(url.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm")):
        # If MP4 already
        if "mp4" in content_type or url.lower().endswith(".mp4"):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tmp.write(data)
            tmp.close()
            return tmp.name, "video/mp4"
        # If ffmpeg available, transcode input to mp4
        if _ffmpeg_available():
            in_tmp = tempfile.NamedTemporaryFile(delete=False)
            in_tmp.write(data)
            in_tmp.close()
            out_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            out_tmp.close()
            loop = asyncio.get_running_loop()

            def _run_ffmpeg(inp, out):
                # use -y to overwrite, copy audio/video if possible, fallback to libx264/aac
                cmd = [
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-i", inp,
                    "-c:v", "libx264", "-c:a", "aac", "-strict", "-2",
                    "-movflags", "+faststart",
                    out
                ]
                return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            proc = await loop.run_in_executor(None, _run_ffmpeg, in_tmp.name, out_tmp.name)
            # cleanup input
            try:
                os.unlink(in_tmp.name)
            except Exception:
                pass
            if proc.returncode == 0:
                return out_tmp.name, "video/mp4"
            else:
                try:
                    os.unlink(out_tmp.name)
                except Exception:
                    pass
                return None, None
        # no ffmpeg: cannot safely transcode
        return None, None

    # Unknown type: fail
    return None, None

# ================== Cog ==================
class RedditPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def clean_label(self, text: str) -> str:
        clean = text.replace("\n", " ").strip()
        return clean[:97] + "..." if len(clean) > 100 else clean

    @app_commands.command(name="reddit", description="Post a tweet from the library to Reddit")
    async def reddit_from_library(self, interaction: discord.Interaction):
        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not channel:
            await interaction.response.send_message("❌ Library channel not found.", ephemeral=True)
            return

        messages = [msg async for msg in channel.history(limit=200)]
        if not messages:
            await interaction.response.send_message("❌ No tweets in the library.", ephemeral=True)
            return

        # Extract combined data (works with embeds created by twitter_feed.py or raw attachments)
        def extract_message_data(msg):
            text = (msg.content or "").strip()
            image_url = None
            attachment_url = None
            tweet_id = None
            media_type = None  # "image" or "video" or None

            if msg.embeds:
                emb = msg.embeds[0]
                if getattr(emb, "description", None):
                    text = emb.description.strip()
                if getattr(emb, "video", None) and getattr(emb.video, "url", None):
                    attachment_url = emb.video.url
                    media_type = "video"
                if getattr(emb, "image", None) and getattr(emb.image, "url", None):
                    image_url = emb.image.url
                    if media_type is None:
                        media_type = "image"
                if getattr(emb, "footer", None) and getattr(emb.footer, "text", None):
                    footer = emb.footer.text
                    if footer.startswith("Tweet ID:"):
                        tweet_id = footer.split(":", 1)[1].strip()

            if msg.attachments:
                att = msg.attachments[0]
                att_url = att.url
                ct = (getattr(att, "content_type", "") or "").lower()
                if ct.startswith("video") or att_url.endswith((".mp4", ".mov", ".webm")):
                    attachment_url = att_url
                    media_type = "video"
                elif ct.startswith("image") or att_url.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    if media_type != "video":
                        image_url = att_url
                        media_type = "image"
                    else:
                        attachment_url = att_url
                else:
                    if not attachment_url:
                        attachment_url = att_url

            return {
                "text": text or "",
                "image_url": image_url,
                "attachment_url": attachment_url,
                "tweet_id": tweet_id,
                "media_type": media_type,
                "message": msg,
            }

        # Group by tweet_id (embed footer must contain "Tweet ID: <id>" for grouping)
        grouped = {}
        order = []
        for msg in messages:
            data = extract_message_data(msg)
            key = data["tweet_id"] or f"msg:{msg.id}"
            if key not in grouped:
                grouped[key] = {
                    "text": data["text"],
                    "image_url": data["image_url"],
                    "attachment_url": data["attachment_url"],
                    "media_type": data["media_type"],
                    "messages": [data["message"]],
                    "tweet_id": data["tweet_id"],
                }
                order.append(key)
            else:
                g = grouped[key]
                if not g["text"] and data["text"]:
                    g["text"] = data["text"]
                # prefer video over image
                if data["media_type"] == "video":
                    g["attachment_url"] = data["attachment_url"]
                    g["media_type"] = "video"
                elif data["media_type"] == "image" and not g["image_url"]:
                    g["image_url"] = data["image_url"]
                    if not g["media_type"]:
                        g["media_type"] = "image"
                if not g["attachment_url"] and data["attachment_url"]:
                    g["attachment_url"] = data["attachment_url"]
                g["messages"].append(data["message"])

        entries = [grouped[k] for k in order[:25]]

        def make_label_from_entry(entry, idx):
            preview = (entry["text"] or "").replace("\n", " ").strip()
            if preview:
                preview = self.clean_label(preview)
            elif entry["media_type"] == "video":
                preview = "Video"
            elif entry["image_url"]:
                preview = "Image"
            elif entry["attachment_url"]:
                preview = "Attachment"
            else:
                preview = "[No text]"
            label = f"#{idx+1} — {preview}"
            return label[:100] or "[No text]"

        # Modal to ask title
        class TitleModal(ui.Modal):
            def __init__(self, entry, idx):
                super().__init__(title="Enter Reddit post title")
                self.entry = entry
                self.idx = idx
                self.title_input = ui.TextInput(label="Title (max 300 chars)", style=discord.TextStyle.short, max_length=300)
                self.add_item(self.title_input)

            async def on_submit(self, modal_inter: discord.Interaction):
                title = self.title_input.value.strip() or f"Library post #{self.idx+1}"
                await modal_inter.response.send_message("Choose a subreddit:", view=SubredditView(self.entry, self.idx, title), ephemeral=True)

        # Tweet selection
        class TweetSelect(ui.Select):
            def __init__(self, entries):
                options = [
                    discord.SelectOption(label=make_label_from_entry(entry, i), value=str(i))
                    for i, entry in enumerate(entries)
                ]
                super().__init__(placeholder="Choose a tweet...", options=options, min_values=1, max_values=1)
                self.entries = entries

            async def callback(self, interaction2: discord.Interaction):
                idx = int(self.values[0])
                entry = self.entries[idx]
                await interaction2.response.send_modal(TitleModal(entry, idx))

        class TweetView(ui.View):
            def __init__(self, entries):
                super().__init__(timeout=120)
                self.add_item(TweetSelect(entries))

        # Subreddit selection
        class SubredditSelect(ui.Select):
            def __init__(self, entry, idx, title):
                options = [discord.SelectOption(label=sub, value=sub) for sub in SUBREDDITS[:25]]
                super().__init__(placeholder="Choose a subreddit...", options=options, min_values=1, max_values=1)
                self.entry = entry
                self.idx = idx
                self.title = title

            async def callback(self, interaction3: discord.Interaction):
                subreddit_name = self.values[0]
                entry = self.entry

                embed = discord.Embed(title=self.title[:300], color=discord.Color.blurple())
                if entry["text"]:
                    embed.add_field(name="Content", value=entry["text"][:1024], inline=False)
                if entry["media_type"] == "video" and entry["attachment_url"]:
                    embed.add_field(name="Video", value="(will upload actual video)", inline=False)
                elif entry["image_url"]:
                    embed.set_image(url=entry["image_url"])
                elif entry["attachment_url"]:
                    embed.add_field(name="Attachment", value=entry["attachment_url"], inline=False)
                embed.set_footer(text=f"Subreddit: r/{subreddit_name}")

                await interaction3.response.send_message("Preview — confirm before posting:", embed=embed, view=ConfirmView(entry, self.idx, self.title, subreddit_name), ephemeral=True)

        class SubredditView(ui.View):
            def __init__(self, entry, idx, title):
                super().__init__(timeout=120)
                self.add_item(SubredditSelect(entry, idx, title))

        # Confirm / Cancel with robust media handling
        class ConfirmView(ui.View):
            def __init__(self, entry, idx, title, subreddit_name):
                super().__init__(timeout=120)
                self.entry = entry
                self.idx = idx
                self.title = title
                self.subreddit_name = subreddit_name

            @ui.button(label="Confirm", style=discord.ButtonStyle.success)
            async def confirm(self, interaction4: discord.Interaction, button: ui.Button):
                await interaction4.response.defer(ephemeral=True)
                session = aiohttp.ClientSession()
                media_tmp_path = None
                try:
                    subreddit_obj = await reddit.subreddit(self.subreddit_name, fetch=True)
                    submission = None

                    # Prefer attachment_url (video) else image_url
                    media_url = self.entry.get("attachment_url") or self.entry.get("image_url")
                    if media_url:
                        media_tmp_path, content_type = await download_media_to_temp(media_url, session)
                        if not media_tmp_path:
                            # if download/transcode failed, abort (no external links)
                            await interaction4.followup.send("❌ Cannot download or transcode media (ffmpeg required for some videos). Post aborted.", ephemeral=True)
                            return

                        # Decide how to post based on file suffix / content_type
                        lower = media_tmp_path.lower()
                        if lower.endswith(".mp4") or (content_type and content_type.startswith("video")):
                            # submit as video
                            try:
                                submission = await subreddit_obj.submit_video(title=self.title[:300], video_path=media_tmp_path)
                            except Exception as e:
                                await interaction4.followup.send(f"❌ Video upload failed — post aborted. ({e})", ephemeral=True)
                                return
                        else:
                            # assume image
                            try:
                                submission = await subreddit_obj.submit_image(title=self.title[:300], image_path=media_tmp_path)
                            except Exception as e:
                                await interaction4.followup.send(f"❌ Image upload failed — post aborted. ({e})", ephemeral=True)
                                return
                    else:
                        # text-only post
                        submission = await subreddit_obj.submit(title=self.title[:300], selftext=(self.entry.get("text") or ""))

                    if submission is not None:
                        try:
                            await submission.load()
                        except Exception:
                            pass
                        permalink = getattr(submission, "permalink", None)
                        post_url = f"https://reddit.com{permalink}" if permalink else f"https://reddit.com/comments/{getattr(submission, 'id', '')}"
                        await interaction4.followup.send(f"✅ Reddit post published: {post_url}", ephemeral=True)
                    else:
                        await interaction4.followup.send("❌ Unable to obtain submission object.", ephemeral=True)
                except Exception as e:
                    await interaction4.followup.send(f"❌ Reddit error: {e}", ephemeral=True)
                finally:
                    try:
                        if media_tmp_path and os.path.exists(media_tmp_path):
                            os.unlink(media_tmp_path)
                    except Exception:
                        pass
                    await session.close()

            @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction4: discord.Interaction, button: ui.Button):
                await interaction4.response.send_message("Cancelled.", ephemeral=True)

        await interaction.response.send_message("📚 Select a tweet from the library:", view=TweetView(entries), ephemeral=True)

async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
