import os
import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncpraw
import aiohttp
import tempfile
import re

# Import Cog Twitter
from commands.twitter_feed import TwitterFeedListener

# ================== Config Reddit ==================
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "1401352070505824306"))

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

    @app_commands.command(name="reddit", description="Choisir un tweet depuis la bibliothèque et poster sur Reddit")
    async def reddit_from_library(self, interaction: discord.Interaction):
        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        messages = await channel.history(limit=50).flatten()  # On récupère les 50 derniers tweets

        if not messages:
            await interaction.response.send_message("❌ La bibliothèque est vide.", ephemeral=True)
            return

        # Préparer les options pour le select menu
        options = []
        for msg in messages:
            if not msg.embeds:
                continue
            embed = msg.embeds[0]
            tweet_text = embed.description or "Tweet vide"
            tweet_id = embed.footer.text.replace("Tweet ID: ", "") if embed.footer else str(msg.id)
            options.append(discord.SelectOption(
                label=tweet_text[:40] + ("..." if len(tweet_text)>40 else ""),
                value=str(msg.id)
            ))

        if not options:
            await interaction.response.send_message("❌ Aucun tweet valide dans la bibliothèque.", ephemeral=True)
            return

        class TweetSelect(ui.View):
            def __init__(self):
                super().__init__(timeout=120)
                self.add_item(
                    ui.Select(
                        placeholder="Choisis le tweet à poster...",
                        options=options,
                        custom_id="tweet_select"
                    )
                )
                self.add_item_callback(self.children[0])

            def add_item_callback(self, select):
                select.callback = self.select_callback

            async def select_callback(self, interaction2: discord.Interaction):
                values = interaction2.data.get("values", [])
                msg_id = int(values[0]) if values else None
                if not msg_id:
                    await interaction2.response.send_message("❌ Pas de tweet sélectionné.", ephemeral=True)
                    return

                # Récupérer le message
                tweet_msg = await channel.fetch_message(msg_id)
                embed = tweet_msg.embeds[0]
                text = embed.description
                media_url = embed.image.url if embed.image else None

                await interaction2.response.defer()

                try:
                    subreddit_name = "test"  # ici tu peux mettre un choix fixe ou ajouter un menu de subreddits
                    subreddit_obj = await reddit.subreddit(subreddit_name, fetch=True)

                    if media_url:
                        # On gère uniquement les images pour simplifier
                        async with aiohttp.ClientSession() as session:
                            async with session.get(media_url) as resp:
                                if resp.status == 200:
                                    tmp_file = tempfile.NamedTemporaryFile(delete=False)
                                    tmp_file.write(await resp.read())
                                    tmp_file.close()
                                    submission = await subreddit_obj.submit_image(
                                        title=text[:300],
                                        image_path=tmp_file.name
                                    )
                                    os.unlink(tmp_file.name)
                    else:
                        submission = await subreddit_obj.submit(title=text[:300], selftext=text)

                    await submission.load()  # important pour avoir le permalink
                    await interaction2.followup.send(
                        f"✅ Post Reddit publié : https://reddit.com{submission.permalink}",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction2.followup.send(f"❌ Erreur Reddit : {e}", ephemeral=True)

        await interaction.response.send_message("Sélectionne le tweet à poster :", view=TweetSelect(), ephemeral=True)


async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
