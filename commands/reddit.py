import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import os
import asyncpraw

# Récupérer les variables d'environnement directement ici
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

# Initialise Reddit avec asyncpraw
reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
    user_agent=f"discord:mybot:v1.0 (by u/{REDDIT_USERNAME})",
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

        # Charger la soumission pour accéder à permalink et autres attributs
        await submission.load()

        await interaction.followup.send(f"✅ Post publié avec succès : https://reddit.com{submission.permalink}")

    except Exception as e:
        await interaction.followup.send(f"❌ Une erreur est survenue : `{e}`", ephemeral=True)

# Setup obligatoire
async def setup(bot: commands.Bot):
    bot.tree.add_command(reddit_command)

