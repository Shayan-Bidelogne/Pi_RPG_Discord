import discord
from discord import app_commands
from discord.ext import commands
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Utiliser un scope permettant l'écriture sur Google Drive
SCOPES = ["https://www.googleapis.com/auth/drive"]  # Permet de lire et écrire sur Google Drive

GAME_FOLDER_ID = "1AA-hk-fwkdkzKroc4GsgitHmoWMcVuZ9"  # ID du dossier "Jeu"

from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = 'credentials.json'  # ton fichier JSON ici

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)



drive_service = get_drive_service()

# 🔁 Fonction récursive pour lister tous les dossiers enfants
def get_all_child_folder_ids(parent_id):
    folder_ids = [parent_id]
    queue = [parent_id]
    while queue:
        current = queue.pop(0)
        response = drive_service.files().list(
            q=f"'{current}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            fields="files(id)"
        ).execute()
        folders = response.get("files", [])
        for folder in folders:
            folder_ids.append(folder["id"])
            queue.append(folder["id"])
    return folder_ids

@discord.app_commands.command(name="get", description="Get a file from the 'Jeu' folder and all its subfolders")
@app_commands.describe(filename="The name of the file you want to retrieve (without extension)")
async def get_file(interaction: discord.Interaction, filename: str):
    await interaction.response.defer()

    try:
        # Obtenir tous les IDs de dossiers enfants
        folder_ids = get_all_child_folder_ids(GAME_FOLDER_ID)
        folder_query = " or ".join([f"'{fid}' in parents" for fid in folder_ids])

        # Chercher les fichiers dans tous les sous-dossiers
        query = f"({folder_query}) and name contains '{filename}' and trashed = false"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name, webViewLink, parents)"
        ).execute()

        files = results.get('files', [])

        if not files:
            await interaction.followup.send(
                f"❌ Nothing with **{filename}** try something else"
            )
        else:
            file_list = "\n".join(
                [f"**{file['name']}** - [Lien]({file['webViewLink']})" for file in files]
            )
            await interaction.followup.send(
                f"✅ Files found :\n{file_list}"
            )

    except Exception as e:
        print(f"Error retrieving file: {e}")
        await interaction.followup.send(
            "❌ Une erreur est survenue lors de la récupération du fichier."
        )

# Setup
async def setup(bot: commands.Bot):
    bot.tree.add_command(get_file)
