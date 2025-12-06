import os
import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncpraw
import aiohttp
import tempfile
import re

from commands.twitter_feed import TwitterFeedListener  # Cog Twitter

# ================== Config Reddit ==================
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "123456789012345678"))  # Bibliothèque tweets
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

    @app_commands.command(
        name="reddit",
        description="Choisir un tweet depuis la bibliothèque et le poster sur Reddit"
    )
    async def reddit_from_library(self, interaction: discord.Interaction):
        # Récupérer le channel bibliothèque
        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not channel:
            await interaction.response.send_message("❌ Channel bibliothèque introuvable.", ephemeral=True)
            return

        # Récupérer les derniers messages (async generator)
        messages = []
        async for msg in channel.history(limit=50):
            messages.append(msg)

        if not messages:
            await interaction.response.send_message("❌ Aucun tweet dans la bibliothèque.", ephemeral=True)
            return

        # Créer menu select pour choisir le tweet
        class TweetSelect(ui.View):
            def __init__(self):
                super().__init__(timeout=120)
                self.add_item(
                    ui.Select(
                        placeholder="Choisis le tweet à poster...",
                        options=[
                            discord.SelectOption(label=msg.content[:100], value=str(i))
                            for i, msg in enumerate(messages)
                        ],
                        custom_id="tweet_select"
                    )
                )
                self.add_item_callback(self.children[0])

            def add_item_callback(self, select):
                select.callback = self.select_callback

            async def select_callback(self, interaction2: discord.Interaction):
                values = interaction2.data.get("values", [])
                idx = int(values[0]) if values else None
                if idx is None or idx >= len(messages):
                    await interaction2.response.send_message("❌ Sélection invalide.", ephemeral=True)
                    return

                msg = messages[idx]

                # Récupérer le contenu et les médias
                text = msg.content
                media_info = None
                if msg.attachments:
                    attachment = msg.attachments[0]  # On prend le premier media
                    media_info = attachment

                # Embed confirmation Discord
                embed = discord.Embed(description=text, color=discord.Color.orange())
                if media_info:
                    embed.set_image(url=media_info.url)

                # Menu select subreddit
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
                        select.callback = self.subreddit_callback

                    async def subreddit_callback(self, interaction3: discord.Interaction):
                        values = interaction3.data.get("values", [])
                        subreddit_name = values[0] if values else None
                        if not subreddit_name:
                            await interaction3.response.send_message("❌ Pas de subreddit sélectionné.", ephemeral=True)
                            return

                        await interaction3.response.defer()
                        try:
                            subreddit_obj = await reddit.subreddit(subreddit_name, fetch=True)

                            # Poster média si existant
                            if media_info:
                                if media_info.content_type.startswith("image"):
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get(media_info.url) as resp:
                                            if resp.status == 200:
                                                tmp_file = tempfile.NamedTemporaryFile(delete=False)
                                                tmp_file.write(await resp.read())
                                                tmp_file.close()
                                                submission = await subreddit_obj.submit_image(
                                                    title=text[:300], image_path=tmp_file.name
                                                )
                                                os.unlink(tmp_file.name)
                                elif media_info.content_type.startswith("video"):
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get(media_info.url) as resp:
                                            if resp.status == 200:
                                                tmp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                                                tmp_file.write(await resp.read())
                                                tmp_file.close()
                                                submission = await subreddit_obj.submit_video(
                                                    title=text[:300], video_path=tmp_file.name
                                                )
                                                os.unlink(tmp_file.name)
                            else:
                                submission = await subreddit_obj.submit(title=text[:300], selftext=text)

                            await interaction3.followup.send(
                                f"✅ Post Reddit publié : https://reddit.com{submission.permalink}", ephemeral=True
                            )
                        except Exception as e:
                            await interaction3.followup.send(f"❌ Erreur Reddit : {e}", ephemeral=True)

                await interaction2.followup.send(embed=embed, view=SubredditSelect(), ephemeral=True)

        await interaction.response.send_message(
            "✅ Choisis le tweet à poster sur Reddit :",
            view=TweetSelect(),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
