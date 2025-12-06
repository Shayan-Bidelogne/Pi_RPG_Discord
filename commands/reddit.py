import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import os
import asyncpraw

# Variables d'environnement
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

# Initialisation Reddit
reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
    user_agent=f"discord:mybot:v1.0 (by u/{REDDIT_USERNAME})",
)

@app_commands.command(name="reddit", description="Poster sur Reddit un message texte, une image ou une vidéo")
@app_commands.describe(
    title="Titre du post",
    subreddit="Nom du subreddit (sans /r/)",
    message="Contenu texte du post (optionnel)",
    media="Image ou vidéo (optionnel)"
)
async def reddit_command(
    interaction: discord.Interaction,
    title: str,
    subreddit: str,
    message: Optional[str] = None,
    media: Optional[discord.Attachment] = None,
):

    await interaction.response.defer(thinking=True)

    try:
        sub = await reddit.subreddit(subreddit, fetch=True)

        # --- Cas média (image ou vidéo) ---
        if media:
            file_path = f"/tmp/{interaction.id}_{media.filename}"
            await media.save(file_path)

            is_video = media.content_type.startswith("video")

            if is_video:
                # Upload vidéo Reddit via submit()
                submission = await sub.submit(
                    title=title,
                    selftext=message or "",
                    video_file=file_path,
                )
            else:
                # Upload image Reddit
                submission = await sub.submit_image(
                    title=title,
                    image_path=file_path
                )

            os.remove(file_path)

        # --- Cas texte seul ---
        elif message:
            submission = await sub.submit(title=title, selftext=message)

        else:
            await interaction.followup.send("❌ Tu dois fournir un média ou un message.")
            return

        await submission.load()
        await interaction.followup.send(f"✅ Post publié : https://reddit.com{submission.permalink}")

    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : `{e}`", ephemeral=True)

async def setup(bot: commands.Bot):
    bot.tree.add_command(reddit_command)