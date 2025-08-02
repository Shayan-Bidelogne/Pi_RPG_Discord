import discord
from discord import app_commands
from discord.ext import commands
import os
import io
import json

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Scopes Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']
TARGET_FOLDER_ID = "1RAOczLrtnsSzEQHOzV3ZyUnJS0iroF7R"

def get_drive_service():
    json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not json_str:
        raise RuntimeError("La variable d’environnement GOOGLE_CREDENTIALS_JSON est manquante.")
    
    try:
        credentials_info = json.loads(json_str.replace('\\n', '\n'))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Erreur de décodage JSON des identifiants : {e}")

    creds = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

drive_service = get_drive_service()

@discord.app_commands.command(name="push", description="Upload a file to Google Drive")
@app_commands.describe(file="The file you want to upload (.png only)")
async def push(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)

    if not file.filename.lower().endswith(".png"):
        await interaction.followup.send("❌ Seuls les fichiers `.png` sont autorisés.", ephemeral=True)
        return

    file_bytes = await file.read()
    file_stream = io.BytesIO(file_bytes)
    media = MediaIoBaseUpload(file_stream, mimetype=file.content_type, resumable=True)

    try:
        uploaded_file = drive_service.files().create(
            body={
                "name": file.filename,
                "parents": [TARGET_FOLDER_ID]
            },
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        await interaction.channel.send(
            f"🎉 **Fichier uploadé !**\n"
            f"👤 Utilisateur : {interaction.user.mention}\n"
            f"📁 Nom du fichier : **{file.filename}**\n"
            f"🔗 Lien : {uploaded_file['webViewLink']}"
        )
    except Exception as e:
        print(f"Erreur lors de l'upload : {e}")
        await interaction.followup.send(
            "❌ Une erreur est survenue lors de l'envoi du fichier sur Google Drive.",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    bot.tree.add_command(push)
