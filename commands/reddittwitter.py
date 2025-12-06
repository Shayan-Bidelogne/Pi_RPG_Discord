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

# Config
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "1439549538556973106"))
SUBREDDITS = ["test", "mySubreddit1", "mySubreddit2"]

# Reddit client
reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
    user_agent=f"discord:pi-rpg-bot:v1 (by u/{REDDIT_USERNAME})",
)

VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".m4v")
IMAGE_CT_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None

def _ffmpeg_block(in_path: str, out_path: str) -> bool:
    cmd = ["ffmpeg","-hide_banner","-loglevel","error","-y","-i",in_path,"-c:v","libx264","-c:a","aac","-movflags","+faststart",out_path]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode == 0

async def _transcode_mp4(in_path: str, out_path: str) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _ffmpeg_block, in_path, out_path)

async def _save_tmp(data: bytes, suffix: str) -> str:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        f.write(data)
    finally:
        f.close()
    return f.name

async def download_and_prepare_media(url: str, filename_hint: str = "") -> tuple:
    """
    Download and return (path, kind) where kind in ("video","image").
    Prioritise filename_hint extension (ex: ID.mp4).
    Transcodes to mp4 if needed and ffmpeg available.
    """
    hint_ext = (os.path.splitext((filename_hint or "").split("?")[0])[1] or "").lower()

    async with aiohttp.ClientSession() as s:
        # try HEAD for content-type
        try:
            async with s.head(url, timeout=10) as r:
                ctype = (r.headers.get("Content-Type") or "").split(";",1)[0].lower()
        except Exception:
            ctype = ""
        # download bytes
        try:
            async with s.get(url, timeout=60) as r:
                if r.status != 200:
                    return None, None
                data = await r.read()
        except Exception:
            return None, None

    lower = url.lower()

    # If filename_hint signals video, force video flow
    if hint_ext in VIDEO_EXTS:
        # if already mp4 -> save
        if hint_ext == ".mp4" or "mp4" in (ctype or "") or lower.endswith(".mp4"):
            return await _save_tmp(data, ".mp4"), "video"
        if _ffmpeg_available():
            in_path = await _save_tmp(data, hint_ext or ".tmp")
            out_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            out_path = out_tmp.name
            out_tmp.close()
            ok = await _transcode_mp4(in_path, out_path)
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

    # image detection
    if ctype.startswith("image") or any(lower.endswith(e) for e in (".png",".jpg",".jpeg",".webp",".gif")) or hint_ext in (".png",".jpg",".jpeg",".webp",".gif"):
        ext = IMAGE_CT_EXT.get(ctype)
        if not ext:
            for e in (".png",".jpg",".jpeg",".webp",".gif"):
                if (filename_hint or lower).lower().endswith(e) or lower.endswith(e):
                    ext = e; break
        if not ext:
            ext = ".jpg"
        return await _save_tmp(data, ext), "image"

    # fallback video detection
    if ctype.startswith("video") or any(lower.endswith(e) for e in VIDEO_EXTS):
        if "mp4" in (ctype or "") or lower.endswith(".mp4"):
            return await _save_tmp(data, ".mp4"), "video"
        if _ffmpeg_available():
            in_ext = os.path.splitext(filename_hint or lower)[1] or ".tmp"
            in_path = await _save_tmp(data, in_ext)
            out_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            out_path = out_tmp.name
            out_tmp.close()
            ok = await _transcode_mp4(in_path, out_path)
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

    return None, None

class RedditPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _short(self, t: str) -> str:
        return (t.replace("\n"," ")[:97] + "...") if t and len(t) > 100 else (t or "[No text]")

    @app_commands.command(name="reddit", description="Post from library to Reddit")
    async def reddit_from_library(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not channel:
            await interaction.followup.send("Library channel not found.", ephemeral=True); return

        messages = [m async for m in channel.history(limit=200)]

        # simple extractor: prefer attachments (filename -> ID.mp4), fallback to embed image/url
        def extract(m):
            text = (m.content or "").strip()
            tweet_id = None
            image = None
            attachment_url = None
            filename = ""
            if m.attachments:
                a = m.attachments[0]
                attachment_url = getattr(a, "url", None) or getattr(a, "proxy_url", None)
                filename = getattr(a, "filename", "") or ""
            if m.embeds and not attachment_url:
                emb = m.embeds[0]
                if getattr(emb, "description", None):
                    text = emb.description.strip()
                emb_image = getattr(getattr(emb, "image", None), "url", None)
                emb_footer = getattr(getattr(emb, "footer", None), "text", None)
                if emb_image:
                    image = emb_image
                if emb_footer and isinstance(emb_footer, str) and emb_footer.startswith("Tweet ID:"):
                    tweet_id = emb_footer.split(":",1)[1].strip()
            return {"text": text, "image": image, "attachment_url": attachment_url, "filename": filename, "tweet_id": tweet_id, "message": m}

        items = [extract(m) for m in messages]
        # group by tweet_id when present
        grouped = {}
        for it in items:
            key = it["tweet_id"] or f"msg:{it['message'].id}"
            if key not in grouped:
                grouped[key] = {"text": it["text"], "image": it["image"], "attachment_url": it["attachment_url"], "filename": it["filename"], "messages":[it["message"]]
                }
            else:
                g = grouped[key]
                if not g["text"] and it["text"]:
                    g["text"] = it["text"]
                if not g["attachment_url"] and it["attachment_url"]:
                    g["attachment_url"] = it["attachment_url"]; g["filename"] = it["filename"]
                if not g["image"] and it["image"]:
                    g["image"] = it["image"]
                g["messages"].append(it["message"])

        entries = list(grouped.values())[:25]
        if not entries:
            await interaction.followup.send("No items in library.", ephemeral=True); return

        # minimal UI: select -> title modal -> subreddit select -> confirm (downloads/uploads)
        class TitleModal(ui.Modal):
            def __init__(self, entry_index:int):
                super().__init__(title="Reddit title")
                self.entry_index = entry_index
                self.title_input = ui.TextInput(label="Title", max_length=300)
                self.add_item(self.title_input)
            async def on_submit(self, modal_inter):
                title = self.title_input.value.strip() or f"Library post #{self.entry_index+1}"
                await modal_inter.response.send_message("Choose subreddit:", view=SubredditView(self.entry_index, title), ephemeral=True)

        class ConfirmView(ui.View):
            def __init__(self, entry_index:int, title:str, subreddit:str):
                super().__init__(timeout=120)
                self.entry_index = entry_index; self.title = title; self.subreddit = subreddit

            @ui.button(label="Confirm & Post", style=discord.ButtonStyle.success)
            async def confirm(self, i:discord.Interaction, b:ui.Button):
                await i.response.defer(ephemeral=True)
                entry = entries[self.entry_index]
                # prefer discord attachment file with filename_hint
                candidate_url = entry.get("attachment_url") or entry.get("image")
                filename_hint = entry.get("filename") or ""
                media_path, kind = None, None
                if candidate_url:
                    media_path, kind = await download_and_prepare_media(candidate_url, filename_hint=filename_hint)
                try:
                    subreddit_obj = await reddit.subreddit(self.subreddit, fetch=True)
                    if media_path and kind == "video":
                        await subreddit_obj.submit_video(title=self.title[:300], video_path=media_path)
                    elif media_path and kind == "image":
                        await subreddit_obj.submit_image(title=self.title[:300], image_path=media_path)
                    else:
                        text = (entry.get("text") or "").strip()
                        if not text:
                            await i.followup.send("No media or text to post — aborted.", ephemeral=True); return
                        await subreddit_obj.submit(title=self.title[:300], selftext=text)
                except Exception as e:
                    await i.followup.send(f"Reddit error: {e}", ephemeral=True); return
                finally:
                    if media_path and os.path.exists(media_path):
                        try: os.unlink(media_path)
                        except Exception: pass
                await i.followup.send("✅ Posted to Reddit.", ephemeral=True)

            @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, i:discord.Interaction, b:ui.Button):
                await i.response.send_message("Cancelled.", ephemeral=True)

        class SubredditView(ui.View):
            def __init__(self, entry_index:int, title:str):
                super().__init__(timeout=120)
                self.entry_index = entry_index; self.title = title
                self.add_item(SubredditSelect(entry_index, title))

        class SubredditSelect(ui.Select):
            def __init__(self, entry_index:int, title:str):
                opts = [discord.SelectOption(label=s, value=s) for s in SUBREDDITS[:25]]
                super().__init__(placeholder="Choose subreddit", options=opts, min_values=1, max_values=1)
                self.entry_index = entry_index; self.title = title
            async def callback(self, interaction3):
                sub = self.values[0]
                await interaction3.response.send_message("Ready to post — confirm:", view=ConfirmView(self.entry_index, self.title, sub), ephemeral=True)

        class Select(ui.Select):
            def __init__(self):
                opts = []
                for i,e in enumerate(entries):
                    label = self._label(i,e)
                    opts.append(discord.SelectOption(label=label, value=str(i)))
                super().__init__(placeholder="Choose item...", options=opts, min_values=1, max_values=1)
            def _label(self, i, e):
                text = e.get("text") or ""
                if text: return f"#{i+1} — {text[:60].replace('\\n',' ')}"
                if e.get("attachment_url"): return f"#{i+1} — Attachment"
                if e.get("image"): return f"#{i+1} — Image"
                return f"#{i+1} — [No text]"
            async def callback(self, interaction2):
                idx = int(self.values[0])
                entry = entries[idx]
                # simple preview
                emb = discord.Embed(title=self._label(idx,entry)[:256])
                if entry.get("text"):
                    emb.add_field(name="Content", value=entry["text"][:1024], inline=False)
                if entry.get("image"):
                    emb.set_image(url=entry["image"])
                elif entry.get("attachment_url"):
                    emb.add_field(name="Attachment", value=entry["filename"] or entry["attachment_url"], inline=False)
                await interaction2.response.send_message("Preview:", embed=emb, view=PreviewToModal(idx), ephemeral=True)

        class PreviewToModal(ui.View):
            def __init__(self, idx:int):
                super().__init__(timeout=120)
                self.idx = idx
            @ui.button(label="Set Title & Post", style=discord.ButtonStyle.primary)
            async def go(self, i:discord.Interaction, b:ui.Button):
                await i.response.send_modal(TitleModal(self.idx))
            @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, i:discord.Interaction, b:ui.Button):
                await i.response.send_message("Cancelled.", ephemeral=True)

        v = ui.View(timeout=120)
        v.add_item(Select())
        await interaction.followup.send("Select an item to post:", view=v, ephemeral=True)

async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
