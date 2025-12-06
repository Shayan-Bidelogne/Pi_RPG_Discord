import os
import shutil
import asyncio
import subprocess
import tempfile

import discord
from discord import app_commands, ui
from discord.ext import commands
import aiohttp
import asyncpraw

# ================== Config ==================
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "1439549538556973106"))

SUBREDDITS = ["test", "mySubreddit1", "mySubreddit2"]

# ================== Reddit init ==================
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

VIDEO_EXTS = (".mp4", ".mov", ".webm", ".m4v", ".mkv")


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _ffmpeg_transcode_block(in_path: str, out_path: str) -> bool:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-y", "-i", in_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode == 0


async def _transcode_to_mp4(in_path: str, out_path: str) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ffmpeg_transcode_block, in_path, out_path)


async def _save_bytes(data: bytes, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.close()
    return tmp.name


async def _head_get_content_type(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.head(url, timeout=10) as resp:
            c = resp.headers.get("Content-Type")
            if c:
                return c.split(";", 1)[0].lower()
    except Exception:
        pass
    # fallback to small GET if HEAD failed
    try:
        headers = {"Range": "bytes=0-1023"}
        async with session.get(url, headers=headers, timeout=10) as resp:
            c = resp.headers.get("Content-Type")
            if c:
                return c.split(";", 1)[0].lower()
    except Exception:
        pass
    return ""


async def download_and_prepare_media(url: str, filename_hint: str = "") -> tuple:
    """
    Download URL, prepare a temp file and return (path, kind) where kind is "video" or "image".
    Returns (None, None) on failure. Will transcode to mp4 via ffmpeg if necessary.
    """
    async with aiohttp.ClientSession() as session:
        # get content-type
        ctype = await _head_get_content_type(session, url)
        try:
            async with session.get(url, timeout=60) as resp:
                if resp.status != 200:
                    return None, None
                data = await resp.read()
        except Exception:
            return None, None

    lower = url.lower()
    # image detection
    if ctype.startswith("image") or any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
        ext = IMAGE_CT_EXT.get(ctype)
        if not ext:
            # infer from filename hint or url
            for e in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                if (filename_hint or lower).lower().endswith(e) or lower.endswith(e):
                    ext = e
                    break
        if not ext:
            ext = ".jpg"
        path = await _save_bytes(data, ext)
        return path, "image"

    # video detection
    if ctype.startswith("video") or any(lower.endswith(ext) for ext in VIDEO_EXTS):
        # if mp4 already
        if "mp4" in ctype or lower.endswith(".mp4"):
            path = await _save_bytes(data, ".mp4")
            return path, "video"
        # otherwise try transcode to mp4 if ffmpeg available
        if _ffmpeg_available():
            in_ext = os.path.splitext(filename_hint or lower)[1] or ".tmp"
            in_path = await _save_bytes(data, in_ext)
            out_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            out_path = out_tmp.name
            out_tmp.close()
            ok = await _transcode_to_mp4(in_path, out_path)
            try:
                os.unlink(in_path)
            except Exception:
                pass
            if ok and os.path.exists(out_path):
                return out_path, "video"
            else:
                try:
                    if os.path.exists(out_path):
                        os.unlink(out_path)
                except Exception:
                    pass
                return None, None
        # no ffmpeg -> cannot convert
        return None, None

    # unknown
    return None, None


# ================== Cog ==================
class RedditPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def clean_label(self, text: str) -> str:
        clean = text.replace("\n", " ").strip()
        return clean[:97] + "..." if len(clean) > 100 else clean

    @app_commands.command(name="reddit", description="Poster un tweet depuis la bibliothèque sur Reddit")
    async def reddit_from_library(self, interaction: discord.Interaction):
        # Defer immediately to avoid "This interaction failed" during processing
        await interaction.response.defer(ephemeral=True)

        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not channel:
            await interaction.followup.send("❌ Library channel not found.", ephemeral=True)
            return

        messages = [msg async for msg in channel.history(limit=200)]
        if not messages:
            await interaction.followup.send("❌ No tweets in the library.", ephemeral=True)
            return

        # extract message data, prefer attachments over embeds
        def extract_message_data(msg):
            text = (msg.content or "").strip()
            image_url = None
            attachment_url = None
            tweet_id = None
            media_type = None

            # attachments
            if msg.attachments:
                att = msg.attachments[0]
                att_url = getattr(att, "url", None) or getattr(att, "proxy_url", None)
                filename = getattr(att, "filename", "") or ""
                content_type = (getattr(att, "content_type", "") or "").lower()
                # reconstruct CDN URL if needed
                if not att_url and filename:
                    try:
                        ch_id = getattr(msg.channel, "id", None)
                        msg_id = getattr(msg, "id", None)
                        if ch_id and msg_id:
                            att_url = f"https://cdn.discordapp.com/attachments/{ch_id}/{msg_id}/{filename}"
                    except Exception:
                        pass
                if att_url:
                    attachment_url = att_url
                    if content_type.startswith("video") or att_url.lower().endswith(VIDEO_EXTS):
                        media_type = "video"
                    elif content_type.startswith("image") or att_url.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                        media_type = "image"
                        image_url = att_url
                    else:
                        # keep as attachment url, unknown type
                        media_type = media_type or None

            # embeds as fallback (twitter feed)
            if msg.embeds and (not attachment_url):
                emb = msg.embeds[0]
                if getattr(emb, "description", None):
                    text = emb.description.strip()
                emb_video = getattr(getattr(emb, "video", None), "url", None)
                emb_image = getattr(getattr(emb, "image", None), "url", None)
                if emb_video:
                    attachment_url = emb_video
                    media_type = "video"
                elif emb_image:
                    image_url = emb_image
                    media_type = media_type or "image"
                footer = getattr(getattr(emb, "footer", None), "text", None)
                if footer and isinstance(footer, str) and footer.startswith("Tweet ID:"):
                    tweet_id = footer.split(":", 1)[1].strip()

            return {
                "text": text or "",
                "image_url": image_url,
                "attachment_url": attachment_url,
                "tweet_id": tweet_id,
                "media_type": media_type,
                "message": msg,
            }

        # group messages by tweet_id if present
        grouped = {}
        order = []
        for msg in messages:
            d = extract_message_data(msg)
            key = d["tweet_id"] or f"msg:{msg.id}"
            if key not in grouped:
                grouped[key] = {
                    "text": d["text"],
                    "image_url": d["image_url"],
                    "attachment_url": d["attachment_url"],
                    "media_type": d["media_type"],
                    "messages": [d["message"]],
                    "tweet_id": d["tweet_id"],
                }
                order.append(key)
            else:
                g = grouped[key]
                if not g["text"] and d["text"]:
                    g["text"] = d["text"]
                if d["media_type"] == "video":
                    g["attachment_url"] = d["attachment_url"]
                    g["media_type"] = "video"
                elif d["media_type"] == "image" and not g["image_url"]:
                    g["image_url"] = d["image_url"]
                    if not g["media_type"]:
                        g["media_type"] = "image"
                if not g["attachment_url"] and d["attachment_url"]:
                    g["attachment_url"] = d["attachment_url"]
                g["messages"].append(d["message"])

        entries = [grouped[k] for k in order[:25]]

        def make_label(entry, idx):
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
            return label[:100]

        # UI components
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

        class TweetSelect(ui.Select):
            def __init__(self, entries):
                options = [
                    discord.SelectOption(label=make_label(entry, i), value=str(i))
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
                    embed.add_field(name="Video", value="(video will be uploaded from the library)", inline=False)
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
                tmp_path = None
                try:
                    subreddit_obj = await reddit.subreddit(self.subreddit_name, fetch=True)
                    submission = None

                    # Prefer discord attachments present in messages; try each message attachment first
                    media_path = None
                    media_kind = None

                    # Try attachments in original messages first (more reliable)
                    for msg in self.entry.get("messages", []):
                        for att in getattr(msg, "attachments", []):
                            url = getattr(att, "url", None) or getattr(att, "proxy_url", None)
                            filename = getattr(att, "filename", "") or ""
                            if not url and filename:
                                try:
                                    ch_id = getattr(msg.channel, "id", None)
                                    msg_id = getattr(msg, "id", None)
                                    if ch_id and msg_id:
                                        url = f"https://cdn.discordapp.com/attachments/{ch_id}/{msg_id}/{filename}"
                                except Exception:
                                    pass
                            if not url:
                                continue
                            prepared = await download_and_prepare_media(url, filename_hint=filename)
                            if prepared[0]:
                                media_path, media_kind = prepared
                                break
                        if media_path:
                            break

                    # If nothing from attachments, try entry attachment_url/image_url
                    if not media_path:
                        for candidate in (self.entry.get("attachment_url"), self.entry.get("image_url")):
                            if not candidate:
                                continue
                            prepared = await download_and_prepare_media(candidate)
                            if prepared[0]:
                                media_path, media_kind = prepared
                                break

                    if media_path:
                        tmp_path = media_path
                        # post media
                        try:
                            if media_kind == "video":
                                submission = await subreddit_obj.submit_video(title=self.title[:300], video_path=media_path)
                            else:
                                submission = await subreddit_obj.submit_image(title=self.title[:300], image_path=media_path)
                        except Exception as e:
                            await interaction4.followup.send(f"❌ Media upload failed — post aborted. ({e})", ephemeral=True)
                            return
                    else:
                        # no media available, post text if present; else abort
                        text = (self.entry.get("text") or "").strip()
                        if not text:
                            await interaction4.followup.send("❌ No media or text to post — aborted.", ephemeral=True)
                            return
                        submission = await subreddit_obj.submit(title=self.title[:300], selftext=text)

                    if submission:
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
                    if tmp_path:
                        try:
                            if os.path.exists(tmp_path):
                                os.unlink(tmp_path)
                        except Exception:
                            pass

            @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction4: discord.Interaction, button: ui.Button):
                await interaction4.response.send_message("Cancelled.", ephemeral=True)

        # send selection view
        await interaction.followup.send("📚 Select a tweet from the library:", view=TweetView(entries), ephemeral=True)


async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
