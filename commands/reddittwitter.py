import os
import shutil
import asyncio
import subprocess
import tempfile
import re

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

    Prioritise filename_hint extension (ex: ID.mp4) because Discord attachments keep the real filename.
    """
    hint_ext = (os.path.splitext((filename_hint or "").split("?")[0])[1] or "").lower()

    async with aiohttp.ClientSession() as session:
        # first try to HEAD to detect content-type
        ctype = await _head_get_content_type(session, url)
        # then GET the bytes (we need them anyway)
        try:
            async with session.get(url, timeout=60) as resp:
                if resp.status != 200:
                    return None, None
                data = await resp.read()
        except Exception:
            return None, None

    lower = url.lower()

    # If filename hint explicitly signals a video extension, prefer video flow
    if hint_ext in VIDEO_EXTS:
        # if it's already mp4, save directly
        if hint_ext == ".mp4" or ("mp4" in (ctype or "")) or lower.endswith(".mp4"):
            path = await _save_bytes(data, ".mp4")
            return path, "video"
        # else attempt transcode if ffmpeg available
        if _ffmpeg_available():
            in_path = await _save_bytes(data, hint_ext or ".tmp")
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
            try:
                if os.path.exists(out_path):
                    os.unlink(out_path)
            except Exception:
                pass
        return None, None

    # Image detection (explicit)
    if ctype and ctype.startswith("image") or any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")) or hint_ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
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

    # Video detection (fallback if HEAD indicates video or url endswith video ext)
    if (ctype and ctype.startswith("video")) or any(lower.endswith(ext) for ext in VIDEO_EXTS):
        # if mp4 already
        if "mp4" in (ctype or "") or lower.endswith(".mp4"):
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
        # helper to extract text/media/tweet_id from a message (supports embed.video, embed.image & attachments)
        def extract_message_data(msg):
            text = (msg.content or "").strip()
            image_url = None
            attachment_url = None
            tweet_id = None
            filename = ""
            media_type = None  # "image" or "video" or None

            # Prefer embed description(s) for the tweet text (append if both content & embed exist)
            if msg.embeds:
                # sometimes there are multiple embeds; concatenate descriptions
                for emb in msg.embeds:
                    if getattr(emb, "description", None):
                        desc = emb.description.strip()
                        if desc:
                            text = f"{text}\n{desc}".strip() if text else desc
                    # embed media fallback
                    emb_video = getattr(getattr(emb, "video", None), "url", None)
                    emb_image = getattr(getattr(emb, "image", None), "url", None)
                    if emb_video and not attachment_url:
                        attachment_url = emb_video
                        media_type = "video"
                    if emb_image and not image_url:
                        image_url = emb_image
                        media_type = media_type or "image"
                    # footer may contain "Tweet ID: <id>"
                    footer = getattr(getattr(emb, "footer", None), "text", None)
                    if footer and isinstance(footer, str) and footer.startswith("Tweet ID:"):
                        tweet_id = footer.split(":", 1)[1].strip()

            # Attachments: prefer real attachment URLs (these point to Discord CDN)
            if msg.attachments:
                att = msg.attachments[0]
                att_url = getattr(att, "url", None) or getattr(att, "proxy_url", None)
                filename = getattr(att, "filename", "") or ""
                ct = (getattr(att, "content_type", "") or "").lower()

                # If att_url is missing or not an http URL, reconstruct CDN URL as fallback
                if not att_url and filename:
                    try:
                        channel_id = getattr(msg.channel, "id", None)
                        message_id = getattr(msg, "id", None)
                        if channel_id and message_id:
                            att_url = f"https://cdn.discordapp.com/attachments/{channel_id}/{message_id}/{filename}"
                    except Exception:
                        pass

                if att_url:
                    attachment_url = att_url
                    # detect video types from content_type or filename
                    if ct.startswith("video") or filename.lower().endswith((".mp4", ".mov", ".webm")):
                        media_type = "video"
                    elif ct.startswith("image") or filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                        # prefer image unless a video was already detected
                        if media_type != "video":
                            image_url = att_url
                            media_type = "image"
                    else:
                        media_type = media_type or None

                # If tweet_id not set from embed, try to extract it from the attachment filename (e.g. "<tweet_id>.mp4")
                if not tweet_id and filename:
                    m = re.search(r'(\d{5,})', filename)  # tweet ids are long numeric strings; adjust min length if needed
                    if m:
                        tweet_id = m.group(1)

            # If no attachment found, keep embed urls (video preferred)
            if not attachment_url:
                # already handled above when processing embeds
                pass

            return {
                "text": text or "",
                "image_url": image_url,
                "attachment_url": attachment_url,
                "filename": filename,
                "tweet_id": tweet_id,
                "media_type": media_type,
                "message": msg,
            }

        # Group messages by tweet_id when available or by tweet id found in filenames.
        grouped = {}
        order = []
        for msg in messages:
            data = extract_message_data(msg)
            # use tweet_id when present; else fallback to filename-derived id if available; else message id
            key = data["tweet_id"] or (f"file:{data['filename']}" if data.get("filename") else f"msg:{msg.id}")
            if key not in grouped:
                grouped[key] = {
                    "texts": [data["text"]] if data["text"] else [],
                    "image_url": data["image_url"],
                    "attachment_url": data["attachment_url"],
                    "filename": data.get("filename"),
                    "media_type": data["media_type"],
                    "messages": [data["message"]],
                    "tweet_id": data["tweet_id"],
                }
                order.append(key)
            else:
                g = grouped[key]
                # collect any non-empty text parts to join later
                if data["text"] and data["text"] not in g["texts"]:
                    g["texts"].append(data["text"])
                # prefer video attachment over image
                if data["media_type"] == "video":
                    g["attachment_url"] = data["attachment_url"]
                    g["media_type"] = "video"
                    g["filename"] = data.get("filename") or g.get("filename")
                elif data["media_type"] == "image" and not g["image_url"]:
                    g["image_url"] = data["image_url"]
                    if not g["media_type"]:
                        g["media_type"] = "image"
                if not g["attachment_url"] and data["attachment_url"]:
                    g["attachment_url"] = data["attachment_url"]
                g["messages"].append(data["message"])

        # finalize entries: join texts into a single content string and keep original key
        entries = []
        for k in order[:25]:
            g = grouped[k]
            full_text = " ".join(t.strip() for t in g.get("texts", []) if t and t.strip())[:4000]
            entries.append({
                "key": k,
                "text": full_text,
                "image_url": g.get("image_url"),
                "attachment_url": g.get("attachment_url"),
                "filename": g.get("filename"),
                "media_type": g.get("media_type"),
                "messages": g.get("messages"),
                "tweet_id": g.get("tweet_id"),
            })

        # map for stable lookup from select value -> entry
        entry_map = {e["key"]: e for e in entries}

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

        # UI components (Select uses stable key as value)
        class PreviewView(ui.View):
            def __init__(self, entry_key, idx):
                super().__init__(timeout=120)
                self.entry_key = entry_key
                self.idx = idx

            @ui.button(label="Post", style=discord.ButtonStyle.success)
            async def post(self, interaction_p: discord.Interaction, button: ui.Button):
                entry = entry_map.get(self.entry_key)
                if not entry:
                    await interaction_p.response.send_message("Entry lost — try again.", ephemeral=True)
                    return
                await interaction_p.response.send_modal(TitleModal(entry, self.idx))

            @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction_p: discord.Interaction, button: ui.Button):
                await interaction_p.response.send_message("Cancelled preview.", ephemeral=True)

        class TweetSelect(ui.Select):
            def __init__(self, entries):
                options = [
                    discord.SelectOption(label=make_label(entry, i), value=entry["key"])
                    for i, entry in enumerate(entries)
                ]
                super().__init__(placeholder="Choose a tweet...", options=options, min_values=1, max_values=1)
                self.entries = entries

            async def callback(self, interaction2: discord.Interaction):
                try:
                    key = self.values[0]
                    entry = entry_map.get(key)
                    if not entry:
                        await interaction2.response.send_message("Selected entry not found — please retry.", ephemeral=True)
                        return

                    # build preview embed (include debug metadata)
                    preview_title = self.entries[[e["key"] for e in self.entries].index(key)]["text"] if any(e["key"]==key for e in self.entries) else f"Entry"
                    embed = discord.Embed(title=self.clean_label(entry.get("text")[:100]) if entry.get("text") else f"Entry", color=discord.Color.blurple())
                    text = (entry.get("text") or "").strip()
                    if text:
                        embed.add_field(name="Content", value=text[:1024], inline=False)

                    # debug fields to help trace mismatches
                    meta = []
                    if entry.get("tweet_id"):
                        meta.append(f"tweet_id: {entry.get('tweet_id')}")
                    if entry.get("filename"):
                        meta.append(f"filename: {entry.get('filename')}")
                    if meta:
                        embed.add_field(name="Meta", value=" • ".join(meta), inline=False)

                    if entry.get("image_url"):
                        embed.set_image(url=entry.get("image_url"))
                    elif entry.get("media_type") == "video" and entry.get("attachment_url"):
                        try:
                            filename = entry.get("filename") or entry.get("attachment_url").split("/")[-1]
                        except Exception:
                            filename = entry.get("attachment_url")
                        embed.add_field(name="Video", value=f"{filename}", inline=False)
                    elif entry.get("attachment_url"):
                        embed.add_field(name="Attachment", value=entry.get("attachment_url"), inline=False)

                    embed.set_footer(text=f"Selected: {key}")

                    await interaction2.response.send_message("Preview:", embed=embed, view=PreviewView(key, [i for i,e in enumerate(self.entries) if e["key"]==key][0]), ephemeral=True)
                except Exception as e:
                    try:
                        await interaction2.response.send_message(f"Error preparing preview: {e}", ephemeral=True)
                    except Exception:
                        pass

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

                    # First: try to use discord attachments directly (safer than HTTP CDN fetch)
                    media_path = None
                    media_kind = None

                    for msg in self.entry.get("messages", []):
                        for att in getattr(msg, "attachments", []):
                            filename = getattr(att, "filename", "") or ""
                            try:
                                data = await att.read()
                            except Exception:
                                # fallback to URL download if read() fails
                                data = None

                            if data:
                                lower_fn = filename.lower()
                                # video by filename
                                if any(lower_fn.endswith(ext) for ext in VIDEO_EXTS):
                                    if lower_fn.endswith(".mp4"):
                                        media_path = await _save_bytes(data, ".mp4")
                                        media_kind = "video"
                                        break
                                    # transcode non-mp4
                                    if _ffmpeg_available():
                                        in_path = await _save_bytes(data, os.path.splitext(filename)[1] or ".tmp")
                                        out_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                                        out_path = out_tmp.name
                                        out_tmp.close()
                                        ok = await _transcode_to_mp4(in_path, out_path)
                                        try:
                                            os.unlink(in_path)
                                        except Exception:
                                            pass
                                        if ok and os.path.exists(out_path):
                                            media_path = out_path
                                            media_kind = "video"
                                            break
                                        else:
                                            try:
                                                if os.path.exists(out_path):
                                                    os.unlink(out_path)
                                            except Exception:
                                                pass
                                            continue
                                    else:
                                        # cannot transcode -> skip this attachment
                                        continue
                                # image by filename
                                if any(lower_fn.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
                                    ext = None
                                    for e in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                                        if lower_fn.endswith(e):
                                            ext = e; break
                                    if not ext:
                                        ext = ".jpg"
                                    media_path = await _save_bytes(data, ext)
                                    media_kind = "image"
                                    break

                            # if att.read() failed or data None, try fallback to URL via download_and_prepare_media
                            url = getattr(att, "url", None) or getattr(att, "proxy_url", None)
                            if url:
                                prepared = await download_and_prepare_media(url, filename_hint=filename)
                                if prepared[0]:
                                    media_path, media_kind = prepared
                                    break
                        if media_path:
                            break

                    # If still nothing, try entry attachment_url/image_url (embeds)
                    if not media_path:
                        for candidate in (self.entry.get("attachment_url"), self.entry.get("image_url")):
                            if not candidate:
                                continue
                            prepared = await download_and_prepare_media(candidate, filename_hint=self.entry.get("filename") or "")
                            if prepared[0]:
                                media_path, media_kind = prepared
                                break

                    # Upload or text post
                    if media_path:
                        tmp_path = media_path
                        try:
                            if media_kind == "video":
                                submission = await subreddit_obj.submit_video(title=self.title[:300], video_path=media_path)
                            else:
                                submission = await subreddit_obj.submit_image(title=self.title[:300], image_path=media_path)
                        except Exception as e:
                            await interaction4.followup.send(f"❌ Media upload failed — post aborted. ({e})", ephemeral=True)
                            return
                    else:
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
