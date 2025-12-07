import os
import asyncio
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

SUBREDDITS = ["test", "indiegames", "mySubreddit2"]

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
    try:
        headers = {"Range": "bytes=0-1023"}
        async with session.get(url, headers=headers, timeout=10) as resp:
            c = resp.headers.get("Content-Type")
            if c:
                return c.split(";", 1)[0].lower()
    except Exception:
        pass
    return ""


async def download_image(url: str, filename_hint: str = "") -> str:
    async with aiohttp.ClientSession() as session:
        ctype = await _head_get_content_type(session, url)
        try:
            async with session.get(url, timeout=60) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
        except Exception:
            return None

    ext = IMAGE_CT_EXT.get(ctype)
    lower = url.lower()
    if not ext:
        for e in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            if (filename_hint or lower).lower().endswith(e) or lower.endswith(e):
                ext = e
                break
    if not ext:
        ext = ".jpg"
    return await _save_bytes(data, ext)


# ================== Cog ==================
class RedditPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def clean_label(self, text: str) -> str:
        clean = text.replace("\n", " ").strip()
        return clean[:97] + "..." if len(clean) > 100 else clean

    @app_commands.command(name="reddit", description="Poster un tweet depuis la bibliothèque sur Reddit")
    async def reddit_from_library(self, interaction: discord.Interaction):
        # Require role named "1"
        required_role_name = "1"
        member = interaction.user
        roles = getattr(member, "roles", []) or []
        if not any(r.name == required_role_name for r in roles):
            try:
                await interaction.response.send_message(
                    f"❌ Vous devez avoir le rôle @{required_role_name} pour utiliser cette commande.", ephemeral=True
                )
            except Exception:
                await interaction.followup.send(
                    f"❌ Vous devez avoir le rôle @{required_role_name} pour utiliser cette commande.", ephemeral=True
                )
            return

        await interaction.response.defer(ephemeral=True)
        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not channel:
            await interaction.followup.send("❌ Library channel not found.", ephemeral=True)
            return

        messages = [msg async for msg in channel.history(limit=200)]
        if not messages:
            await interaction.followup.send("❌ No tweets in the library.", ephemeral=True)
            return

        # ------------------ extraction ------------------
        def extract_message_data(msg):
            text = (msg.content or "").strip()
            image_url = None
            attachment_url = None
            tweet_id = None
            filename = ""

            if msg.embeds:
                for emb in msg.embeds:
                    if getattr(emb, "description", None):
                        desc = emb.description.strip()
                        if desc:
                            text = f"{text}\n{desc}".strip() if text else desc
                    emb_image = getattr(getattr(emb, "image", None), "url", None)
                    if emb_image and not image_url:
                        image_url = emb_image
                    footer = getattr(getattr(emb, "footer", None), "text", None)
                    if footer and isinstance(footer, str) and footer.startswith("Tweet ID:"):
                        tweet_id = footer.split(":", 1)[1].strip()

            if msg.attachments:
                att = msg.attachments[0]
                att_url = getattr(att, "url", None) or getattr(att, "proxy_url", None)
                filename = getattr(att, "filename", "") or ""
                ct = (getattr(att, "content_type", "") or "").lower()

                if not att_url and filename:
                    try:
                        channel_id = getattr(msg.channel, "id", None)
                        message_id = getattr(msg, "id", None)
                        if channel_id and message_id:
                            att_url = f"https://cdn.discordapp.com/attachments/{channel_id}/{message_id}/{filename}"
                    except Exception:
                        pass

                if att_url:
                    if ct.startswith("image") or filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                        attachment_url = att_url
                        image_url = att_url

            return {
                "text": text or "",
                "image_url": image_url,
                "attachment_url": attachment_url,
                "filename": filename,
                "tweet_id": tweet_id,
                "message": msg,
            }

        grouped = {}
        order = []
        for msg in messages:
            data = extract_message_data(msg)
            key = data["tweet_id"] or (f"file:{data['filename']}" if data.get("filename") else f"msg:{msg.id}")
            if key not in grouped:
                grouped[key] = {
                    "texts": [data["text"]] if data["text"] else [],
                    "image_url": data["image_url"],
                    "attachment_url": data["attachment_url"],
                    "filename": data.get("filename"),
                    "messages": [data["message"]],
                    "tweet_id": data["tweet_id"],
                }
                order.append(key)
            else:
                g = grouped[key]
                if data["text"] and data["text"] not in g["texts"]:
                    g["texts"].append(data["text"])
                if not g["image_url"] and data["image_url"]:
                    g["image_url"] = data["image_url"]
                if not g["attachment_url"] and data["attachment_url"]:
                    g["attachment_url"] = data["attachment_url"]
                if not g.get("filename") and data.get("filename"):
                    g["filename"] = data.get("filename")
                g["messages"].append(data["message"])

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
                "messages": g.get("messages"),
                "tweet_id": g.get("tweet_id"),
            })

        entry_map = {e["key"]: e for e in entries}
        cog = self

        def make_label(entry, idx):
            preview = (entry["text"] or "").replace("\n", " ").strip()
            if preview:
                preview = cog.clean_label(preview)
            elif entry.get("image_url"):
                preview = "Image"
            elif entry.get("attachment_url"):
                preview = "Attachment"
            else:
                preview = "[No text]"
            label = f"#{idx+1} — {preview}"
            return label[:100]

        # ------------------ Modal pour le titre ------------------
        class TitleModal(ui.Modal):
            def __init__(self, entry, idx):
                super().__init__(title="Enter Reddit post title")
                self.entry = entry
                self.idx = idx
                self.title_input = ui.TextInput(label="Title (max 300 chars)", style=discord.TextStyle.short, max_length=300)
                self.add_item(self.title_input)

            async def on_submit(self, modal_inter: discord.Interaction):
                title = self.title_input.value.strip() or f"Library post #{self.idx+1}"
                await modal_inter.response.send_message(
                    "Choose a subreddit:", view=SubredditView(self.entry, self.idx, title), ephemeral=True
                )

        # ------------------ Select subreddit ------------------
        class SubredditSelect(ui.Select):
            def __init__(self, entry, idx, title):
                opts = [discord.SelectOption(label=s, value=s) for s in SUBREDDITS[:25]]
                super().__init__(placeholder="Choose subreddit", options=opts, min_values=1, max_values=1)
                self.entry = entry
                self.idx = idx
                self.title = title

            async def callback(self, interaction3: discord.Interaction):
                subreddit_name = self.values[0]
                subreddit_obj = await reddit.subreddit(subreddit_name, fetch=True)
                if getattr(subreddit_obj, "link_flair_required", False):
                    # si flair requis
                    view = FlairSelectView(self.entry, self.idx, self.title, subreddit_obj, subreddit_name)
                    await interaction3.response.send_message("Subreddit requires flair. Please select one:", view=view, ephemeral=True)
                else:
                    await post_to_reddit(interaction3, self.entry, self.title, subreddit_obj, subreddit_name, flair_id=None)

        class SubredditView(ui.View):
            def __init__(self, entry, idx, title):
                super().__init__(timeout=120)
                self.add_item(SubredditSelect(entry, idx, title))

        # ------------------ Select flair si nécessaire ------------------
        class FlairSelect(ui.Select):
            def __init__(self, entry, idx, title, subreddit_obj, subreddit_name):
                self.entry = entry
                self.idx = idx
                self.title = title
                self.subreddit_obj = subreddit_obj
                self.subreddit_name = subreddit_name
                self.flair_map = {}
                options = []

                async def setup_flairs():
                    flairs = await subreddit_obj.flair.link_templates()
                    if not flairs:
                        return
                    for f in flairs:
                        fid = f['id']
                        text = f.get('text', 'No text')[:100]
                        options.append(discord.SelectOption(label=text, value=fid))
                        self.flair_map[fid] = text

                asyncio.get_event_loop().run_until_complete(setup_flairs())
                super().__init__(
                    placeholder="Choose a flair" if options else "No flairs available",
                    options=options,
                    min_values=1 if options else 0,
                    max_values=1 if options else 0
                )

            async def callback(self, interaction: discord.Interaction):
                flair_id = self.values[0] if self.values else None
                await interaction.response.send_message(f"✅ Flair selected: {self.flair_map.get(flair_id, 'None')}", ephemeral=True)
                await post_to_reddit(interaction, self.entry, self.title, self.subreddit_obj, self.subreddit_name, flair_id)

        class FlairSelectView(ui.View):
            def __init__(self, entry, idx, title, subreddit_obj, subreddit_name):
                super().__init__(timeout=120)
                self.add_item(FlairSelect(entry, idx, title, subreddit_obj, subreddit_name))

        # ------------------ Post helper ------------------
        async def post_to_reddit(interaction, entry, title, subreddit_obj, subreddit_name, flair_id=None):
            tmp_path = None
            try:
                image_path = None
                for msg in entry.get("messages", []):
                    for att in getattr(msg, "attachments", []):
                        filename = getattr(att, "filename", "") or ""
                        ct = (getattr(att, "content_type", "") or "").lower()
                        if ct.startswith("image") or filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                            data = await att.read()
                            if data:
                                ext = next((e for e in (".png",".jpg",".jpeg",".webp",".gif") if filename.lower().endswith(e)), ".jpg")
                                tmp_path = await _save_bytes(data, ext)
                                image_path = tmp_path
                                break
                    if image_path:
                        break

                if not image_path and entry.get("image_url"):
                    tmp_path = await download_image(entry.get("image_url"), filename_hint=entry.get("filename") or "")
                    image_path = tmp_path

                submission = None
                if image_path:
                    submission = await subreddit_obj.submit_image(title=title[:300], image_path=image_path, flair_id=flair_id)
                else:
                    text = (entry.get("text") or "").strip()
                    if not text:
                        await interaction.followup.send("❌ No media or text to post — aborted.", ephemeral=True)
                        return
                    submission = await subreddit_obj.submit(title=title[:300], selftext=text, flair_id=flair_id)

                if submission:
                    await submission.load()
                    permalink = getattr(submission, "permalink", None)
                    post_url = f"https://reddit.com{permalink}" if permalink else f"https://reddit.com/comments/{getattr(submission, 'id', '')}"
                    await interaction.followup.send(f"✅ Reddit post published: {post_url}", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Unable to obtain submission object.", ephemeral=True)
            finally:
                if tmp_path:
                    try:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    except Exception:
                        pass

        # ------------------ Select tweet ------------------
        class TweetSelect(ui.Select):
            def __init__(self, entries):
                options = [
                    discord.SelectOption(label=make_label(entry, i), value=entry["key"])
                    for i, entry in enumerate(entries)
                ]
                super().__init__(placeholder="Choose a tweet...", options=options, min_values=1, max_values=1)
                self.entries = entries

            async def callback(self, interaction2: discord.Interaction):
                key = self.values[0]
                entry = entry_map.get(key)
                if not entry:
                    await interaction2.response.send_message("Entry lost — retry.", ephemeral=True)
                    return
                await interaction2.response.send_modal(TitleModal(entry, [i for i,e in enumerate(self.entries) if e["key"]==key][0]))

        class TweetView(ui.View):
            def __init__(self, entries):
                super().__init__(timeout=120)
                self.add_item(TweetSelect(entries))

        await interaction.followup.send("📚 Select a tweet from the library:", view=TweetView(entries), ephemeral=True)


async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
