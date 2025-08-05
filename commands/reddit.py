import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import os
import asyncpraw
import config

# Initialise Reddit avec asyncpraw
reddit = asyncpraw.Reddit(
    client_id=config.REDDIT_CLIENT_ID,
    client_secret=config.REDDIT_CLIENT_SECRET,
    username=config.REDDIT_USERNAME,
    password=config.REDDIT_PASSWORD,
    user_agent="discord:mybot:v1.0 (by u/{})".format(config.REDDIT_USERNAME),
)

# Slash command /reddit
@app_commands.command(name="reddit", description="Poster sur Reddit un message texte ou une image")
@app_commands.describe(
    title="Titre du post Reddit",
    subreddit="Nom du subreddit sans /r/",
    message="Contenu du post (optionnel pour les images)",
    image="Image à uploader (optionnelle, max 1 image)"
)
async def reddit_command(
    interaction: discord.Interaction,
    title: str,
    subreddit: str,
    message: Optional[str] = None,
    image: Optional[discord.Attachment] = None
):
    await interaction.response.defer(thinking=True)

    try:
        subreddit_obj = await reddit.subreddit(subreddit, fetch=True)

        if image:
            # Enregistrer l'image temporairement
            file_path = f"/tmp/{image.filename}"
            await image.save(file_path)

            submission = await subreddit_obj.submit_image(title=title, image_path=file_path)

            # Supprimer le fichier temporaire
            os.remove(file_path)

        elif message:
            submission = await subreddit_obj.submit(title=title, selftext=message)
        else:
            await interaction.followup.send("❌ Tu dois fournir soit une image, soit un message.", ephemeral=True)
            return

        await interaction.followup.send(f"✅ Post publié avec succès : https://reddit.com{submission.permalink}")

    except Exception as e:
        await interaction.followup.send(f"❌ Une erreur est survenue : `{e}`", ephemeral=True)

# Setup obligatoire
async def setup(bot: commands.Bot):
    bot.tree.add_command(reddit_command)
