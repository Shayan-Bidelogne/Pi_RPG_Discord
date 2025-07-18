import discord
from discord import app_commands
from discord.ext import commands
import os
import io
import config  # Facultatif si tu veux stocker des clés/API ailleurs

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]

# ID du dossier cible sur Google Drive
TARGET_FOLDER_ID = "1RAOczLrtnsSzEQHOzV3ZyUnJS0iroF7R"

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credentials.json'  # ton fichier JSON ici

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)



drive_service = get_drive_service()

# Commande /push
@discord.app_commands.command(name="push", description="Upload a file to Google Drive")
@app_commands.describe(file="The file you want to upload")
async def push(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)

    # Lire le fichier
    file_bytes = await file.read()
    file_stream = io.BytesIO(file_bytes)
    media = MediaIoBaseUpload(file_stream, mimetype=file.content_type, resumable=True)

    try:
        # Upload vers Drive
        uploaded_file = drive_service.files().create(
            body={
                "name": file.filename,
                "parents": [TARGET_FOLDER_ID]
            },
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        print(f"File uploaded successfully: {uploaded_file['webViewLink']}")

        # Annonce dans le salon
        await interaction.channel.send(
            f"🎉 User : {interaction.user.name}\n"
            f"File : **{file.filename}**\n"
            f"🔗 Link : {uploaded_file['webViewLink']}"
        )

    except Exception as e:
        print(f"Error uploading file: {e}")
        await interaction.followup.send(
            "❌ Une erreur est survenue lors de l'envoi du fichier sur Google Drive.",
            ephemeral=True
        )

# Setup pour le bot
async def setup(bot: commands.Bot):
    bot.tree.add_command(push)
