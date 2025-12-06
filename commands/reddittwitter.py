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
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "1439549538556973106"))
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

    # Fonction pour tronquer/normaliser les labels (Discord max 100 chars)
    def clean_label(self, text: str) -> str:
        clean = text.replace("\n", " ").strip()
        return clean[:97] + "..." if len(clean) > 100 else clean

    @app_commands.command(name="reddit", description="Poster un tweet depuis la bibliothèque sur Reddit")
    async def reddit_from_library(self, interaction: discord.Interaction):
        library_channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not library_channel:
            await interaction.response.send_message("❌ Channel bibliothèque introuvable.", ephemeral=True)
            return

        # Récupérer les 50 derniers messages du channel
        messages = [msg async for msg in library_channel.history(limit=50)]
        if not messages:
            await interaction.response.send_message("❌ Aucun tweet dans la bibliothèque.", ephemeral=True)
            return

        # ---------- View pour sélection du tweet ----------
        class TweetSelect(ui.View):
            def __init__(self, messages, clean_label_func):
                super().__init__(timeout=120)
                self.messages = messages
                self.clean_label_func = clean_label_func

                options = []

                def make_label(msg):
                    txt = (msg.content or "").replace("\n", " ").strip()
                    if txt:
                        # reuse existing cleaning logic
                        return self.clean_label_func(txt)
                    # fallback to attachment filename or URL
                    if msg.attachments:
                        att = msg.attachments[0]
                        name = getattr(att, "filename", None) or getattr(att, "url", "") or "Attachment"
                        name = name.replace("\n", " ").strip()
                        if not name:
                            name = "Attachment"
                        return name[:100]
                    # final fallback
                    return "[No text]"
