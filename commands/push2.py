import discord
from discord import app_commands
from discord.ext import commands
import io
import datetime
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credentials.json'
ARCHIVE_FOLDER_ID = "1dFSNiA7_S5FddzsLNhJTX55egCV2fz8a"

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

drive_service = get_drive_service()

def create_drive_folder(name, parent_id):
    folder_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
    return folder['id']

def format_filename(username, original_name):
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{username}_{timestamp}_{original_name}"

async def update_archive_log(username, links):
    log_filename = "archive_log.txt"
    query = f"'{ARCHIVE_FOLDER_ID}' in parents and name = '{log_filename}' and trashed = false"
    results = drive_service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
    files = results.get('files', [])
    
    log_id = None
    content = ""
    if files:
        log_id = files[0]['id']
        file = drive_service.files().get_media(fileId=log_id).execute()
        content = file.decode('utf-8')

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_lines = [f"{now} | {username} | {link}" for link in links]
    full_content = content + "\n" + "\n".join(new_lines)

    file_stream = io.BytesIO(full_content.encode('utf-8'))
    media = MediaIoBaseUpload(file_stream, mimetype='text/plain', resumable=True)

    if log_id:
        drive_service.files().update(fileId=log_id, media_body=media).execute()
    else:
        drive_service.files().create(
            body={"name": log_filename, "parents": [ARCHIVE_FOLDER_ID]},
            media_body=media,
            fields="id"
        ).execute()

@discord.app_commands.command(name="pushfile", description="Upload a file to Drive with auto-archiving.")
@app_commands.describe(file="The file you want to upload")
async def pushfile(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)

    user_name = interaction.user.name
    archive_name = f"push_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_name}"
    folder_id = create_drive_folder(archive_name, ARCHIVE_FOLDER_ID)

    file_bytes = await file.read()
    file_stream = io.BytesIO(file_bytes)
    formatted_name = format_filename(user_name, file.filename)
    media = MediaIoBaseUpload(file_stream, mimetype=file.content_type, resumable=True)

    uploaded = drive_service.files().create(
        body={"name": formatted_name, "parents": [folder_id]},
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    uploaded_link = uploaded["webViewLink"]

    await update_archive_log(user_name, [uploaded_link])

    await interaction.channel.send(
        f"📁 **Fichier archivé pour {user_name}**\n"
        f"📦 Dossier : `{archive_name}`\n"
        f"🔗 Lien : {uploaded_link}"
    )

# Setup
async def setup(bot: commands.Bot):
    bot.tree.add_command(pushfile)
