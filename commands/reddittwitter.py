import os
import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncpraw
import aiohttp
import tempfile
import re

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

    # ---------- Fonction utilitaire pour nettoyer/tronquer le label ----------
    def clean_label(self, text: str, max_length: int = 100) -> str:
        clean = ' '.join(text.split())  # supprime sauts de ligne et espaces multiples
        if not clean:
            clean = "Tweet sans contenu"
        return clean[:max_length]

    # ---------- Commande reddit depuis bibliothèque ----------
    @app_commands.command(name="reddit", description="Poster un tweet depuis la bibliothèque sur Reddit")
    async def reddit_from_library(self, interaction: discord.Interaction):
        # Récupérer les messages du channel bibliothèque
        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not channel:
            await interaction.response.send_message("❌ Channel bibliothèque introuvable.", ephemeral=True)
            return

        # async pour récupérer les messages
        messages = [msg async for msg in channel.history(limit=25)]
        if not messages:
            await interaction.response.send_message("❌ Aucune entrée dans la bibliothèque.", ephemeral=True)
            return

        # ---------- View pour sélection du tweet ----------
        class TweetSelect(ui.View):
            def __init__(self):
                super().__init__(timeout=120)

                options = [
                    discord.SelectOption(
                        label=self.parent.clean_label(msg.content),
                        value=str(i)
                    )
                    for i, msg in enumerate(messages)
                ]

                self.add_item(
                    ui.Select(
                        placeholder="Choisis un tweet...",
                        options=options,
                        custom_id="tweet_select",
                        min_values=1,
                        max_values=1
                    )
                )
                self.add_item_callback(self.children[0])

            def add_item_callback(self, select):
                select.callback = self.select_callback

            async def select_callback(self, select_interaction: discord.Interaction):
                values = select_interaction.data.get("values", [])
                if not values:
                    await select_interaction.response.send_message("❌ Pas de tweet sélectionné.", ephemeral=True)
                    return

                index = int(values[0])
                tweet_msg = messages[index]

                # Construire l'embed pour confirmation
                embed = discord.Embed(
                    description=tweet_msg.content,
                    color=discord.Color.orange(),
                    timestamp=tweet_msg.created_at
                )
                if tweet_msg.attachments:
                    att = tweet_msg.attachments[0]
                    if att.url.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                        embed.set_image(url=att.url)
                    elif att.url.lower().endswith((".mp4", ".mov")):
                        embed.add_field(name="Vidéo jointe", value=att.url)

                # ---------- View pour choix du subreddit ----------
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
                                custom_id="subreddit_select",
                                min_values=1,
                                max_values=1
                            )
                        )
                        self.add_item_callback(self.children[0])

                    def add_item_callback(self, select):
                        select.callback = self.select_subreddit

                    async def select_subreddit(self, subreddit_interaction: discord.Interaction):
                        values = subreddit_interaction.data.get("values", [])
                        subreddit_name = values[0] if values else None
                        if not subreddit_name:
                            await subreddit_interaction.response.send_message("❌ Pas de subreddit sélectionné.", ephemeral=True)
                            return

                        await subreddit_interaction.response.defer()
                        try:
                            subreddit_obj = await reddit.subreddit(subreddit_name, fetch=True)

                            # Gestion média
                            if tweet_msg.attachments:
                                att = tweet_msg.attachments[0]
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(att.url) as resp:
                                        if resp.status == 200:
                                            tmp_file = tempfile.NamedTemporaryFile(delete=False)
                                            tmp_file.write(await resp.read())
                                            tmp_file.close()

                                            if att.url.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
                                                submission = await subreddit_obj.submit_image(
                                                    title=tweet_msg.content[:300],
                                                    image_path=tmp_file.name
                                                )
                                            else:
                                                submission = await subreddit_obj.submit_video(
                                                    title=tweet_msg.content[:300],
                                                    video_path=tmp_file.name
                                                )
                                            os.unlink(tmp_file.name)
                            else:
                                submission = await subreddit_obj.submit(
                                    title=tweet_msg.content[:300],
                                    selftext=tweet_msg.content
                                )

                            await subreddit_interaction.followup.send(
                                f"✅ Post Reddit publié : https://reddit.com{submission.permalink}",
                                ephemeral=True
                            )
                        except Exception as e:
                            await subreddit_interaction.followup.send(f"❌ Erreur Reddit : {e}", ephemeral=True)

                await select_interaction.response.send_message(
                    "📌 Tweet sélectionné ! Choisis le subreddit :", view=SubredditSelect(), ephemeral=True
                )

        # Envoyer la sélection des tweets
        view = TweetSelect()
        view.parent = self  # pour accéder à clean_label
        await interaction.response.send_message(
            "📚 Sélectionne un tweet dans la bibliothèque :", view=view, ephemeral=True
        )


# ---------- Setup Cog ----------
async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
