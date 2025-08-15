import discord
from discord import app_commands
from discord.ext import commands
import os
import io
import json
import base64
from PIL import Image

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Google Drive scopes
SCOPES = ['https://www.googleapis.com/auth/drive']
TARGET_FOLDER_ID = "1RAOczLrtnsSzEQHOzV3ZyUnJS0iroF7R"

def get_drive_service():
    b64_str = os.getenv("GOOGLE_CREDENTIALS_B64")
    if not b64_str:
        raise RuntimeError("Environment variable GOOGLE_CREDENTIALS_B64 is missing.")
    try:
        json_bytes = base64.b64decode(b64_str)
        credentials_info = json.loads(json_bytes)
    except Exception as e:
        raise RuntimeError(f"Error decoding base64/JSON credentials: {e}")

    creds = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

drive_service = get_drive_service()

def gif_to_spritesheet(gif_bytes: bytes) -> io.BytesIO:
    """Convertit un GIF en spritesheet PNG sans perte"""
    img = Image.open(io.BytesIO(gif_bytes))
    
    frames = []
    try:
        while True:
            frame = img.convert("RGBA")
            frames.append(frame.copy())
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    # Dimensions de la spritesheet (1 ligne avec toutes les frames)
    width = sum(f.width for f in frames)
    height = max(f.height for f in frames)

    spritesheet = Image.new("RGBA", (width, height))
    x_offset = 0
    for frame in frames:
        spritesheet.paste(frame, (x_offset, 0))
        x_offset += frame.width

    output_bytes = io.BytesIO()
    spritesheet.save(output_bytes, format="PNG")  # PNG = aucune perte
    output_bytes.seek(0)
    return output_bytes

@discord.app_commands.command(name="drive", description="Upload a file to Google Drive")
@app_commands.describe(file="The file you want to upload (.png or .gif)")
async def drive(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer(ephemeral=True)

    ext = file.filename.lower().split(".")[-1]
    if ext not in ["png", "gif"]:
        await interaction.followup.send("❌ Only `.png` or `.gif` files are allowed.", ephemeral=True)
        return

    file_bytes = await file.read()

    # Si c’est un GIF → conversion en spritesheet PNG
    if ext == "gif":
        file_stream = gif_to_spritesheet(file_bytes)
        upload_filename = file.filename.rsplit(".", 1)[0] + "_spritesheet.png"
        mime_type = "image/png"
    else:
        file_stream = io.BytesIO(file_bytes)
        upload_filename = file.filename
        mime_type = file.content_type

    media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)

    try:
        uploaded_file = drive_service.files().create(
            body={
                "name": upload_filename,
                "parents": [TARGET_FOLDER_ID]
            },
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        await interaction.channel.send(
            f"🎉 **File uploaded!**\n"
            f"👤 User: {interaction.user.mention}\n"
            f"📁 File name: **{upload_filename}**\n"
            f"🔗 Link: {uploaded_file['webViewLink']}"
        )
    except Exception as e:
        print(f"Upload error: {e}")
        await interaction.followup.send(
            "❌ An error occurred while uploading the file to Google Drive.",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    bot.tree.add_command(drive)
