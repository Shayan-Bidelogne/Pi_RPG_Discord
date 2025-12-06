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
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "YOUR_LIBRARY_CHANNEL_ID"))
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

                options = [
                    discord.SelectOption(
                        label=clean_label_func(msg.content),
                        value=str(i)
                    )
                    for i, msg in enumerate(messages)
                ]

                self.select = ui.Select(
                    placeholder="Choisis un tweet...",
                    options=options,
                    custom_id="tweet_select",
                    min_values=1,
                    max_values=1
                )
                self.add_item(self.select)
                self.select.callback = self.select_callback

            async def select_callback(self, interaction2: discord.Interaction):
                idx = int(self.select.values[0])
                msg = self.messages[idx]

                # Construire media_info si attachments
                media_info = None
                if msg.attachments:
                    att = msg.attachments[0]
                    media_info = {
                        "url": att.url,
                        "type": "photo" if att.content_type.startswith("image") else "video"
                    }

                # Embedding du tweet
                embed = discord.Embed(
                    description=msg.content,
                    color=discord.Color.orange()
                )
                embed.set_author(
                    name=f"Twitter - @{os.environ.get('TWITTER_USERNAME')}",
                    url=f"https://twitter.com/{os.environ.get('TWITTER_USERNAME')}/status/{msg.id}"
                )
                if media_info and media_info["type"] == "photo":
                    embed.set_image(url=media_info["url"])

                await interaction2.response.defer()

                try:
                    subreddit_name = "test"  # ou ajouter un menu pour choisir subreddit
                    subreddit_obj = await reddit.subreddit(subreddit_name, fetch=True)

                    # Poster média si présent
                    if media_info:
                        if media_info["type"] == "photo":
                            async with aiohttp.ClientSession() as session:
                                async with session.get(media_info["url"]) as resp:
                                    if resp.status == 200:
                                        tmp_file = tempfile.NamedTemporaryFile(delete=False)
                                        tmp_file.write(await resp.read())
                                        tmp_file.close()
                                        submission = await subreddit_obj.submit_image(
                                            title=msg.content[:300],
                                            image_path=tmp_file.name
                                        )
                                        os.unlink(tmp_file.name)
                        elif media_info["type"] == "video":
                            async with aiohttp.ClientSession() as session:
                                async with session.get(media_info["url"]) as resp:
                                    if resp.status == 200:
                                        tmp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                                        tmp_file.write(await resp.read())
                                        tmp_file.close()
                                        submission = await subreddit_obj.submit_video(
                                            title=msg.content[:300],
                                            video_path=tmp_file.name
                                        )
                                        os.unlink(tmp_file.name)
                    else:
                        submission = await subreddit_obj.submit(title=msg.content[:300], selftext=msg.content)

                    await interaction2.followup.send(
                        f"✅ Post Reddit publié : https://reddit.com{submission.permalink}",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction2.followup.send(f"❌ Erreur Reddit : {e}", ephemeral=True)

        view = TweetSelect(messages, clean_label_func=self.clean_label)
        await interaction.response.send_message(
            "📚 Sélectionne un tweet dans la bibliothèque :", view=view, ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
