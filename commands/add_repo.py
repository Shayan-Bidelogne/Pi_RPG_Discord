# commands/edit_repo.py

import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp
import base64

if os.path.exists(".env"):
    load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = os.getenv("REPO_OWNER")
REPO_NAME = os.getenv("REPO_NAME")

class EditRepo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="edit_repo", description="Ajouter ou modifier un fichier dans le dépôt GitHub")
    async def edit_repo(self, interaction: discord.Interaction):
        await self.show_folder(interaction, "")

    async def show_folder(self, interaction, path: str):
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    await interaction.response.send_message("❌ Impossible d’accéder au dépôt GitHub.", ephemeral=True)
                    return
                data = await resp.json()

        dirs = [item for item in data if item['type'] == "dir"]

        id_to_item = {}
        options = []

        for i, dir in enumerate(dirs):
            key = f"d{i}"
            id_to_item[key] = dir['path']
            options.append(discord.SelectOption(label=dir['name'], value=key, description="📁 Dossier"))

        if path:
            parent = "/".join(path.split("/")[:-1])
            id_to_item["back"] = parent or ""
            options.append(discord.SelectOption(label="🔙 Retour", value="back", description="Remonter"))

        view = FolderUploadView(options, self, interaction.user, id_to_item, path)

        if interaction.response.is_done():
            await interaction.edit_original_response(content="📂 Choisis un dossier pour ajouter ou remplacer un fichier :", view=view)
        else:
            await interaction.response.send_message(content="📂 Choisis un dossier pour ajouter ou remplacer un fichier :", view=view, ephemeral=True)

    async def upload_file_to_repo(self, interaction: discord.Interaction, folder_path: str, attachment: discord.Attachment):
        filename = attachment.filename
        full_path = f"{folder_path}/{filename}".strip("/")

        file_bytes = await attachment.read()
        content_b64 = base64.b64encode(file_bytes).decode("utf-8")

        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{full_path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Get current file SHA if it exists (needed for replacement)
        sha = None
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    sha = data.get("sha")

        payload = {
            "message": f"Ajout ou mise à jour de {filename}",
            "content": content_b64
        }
        if sha:
            payload["sha"] = sha

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status in (200, 201):
                    await interaction.response.send_message(f"✅ Fichier **{filename}** ajouté ou remplacé dans `{folder_path}`.", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Erreur lors de l’upload du fichier.", ephemeral=True)


class FolderUploadView(discord.ui.View):
    def __init__(self, options, cog, user, id_to_path, current_path):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.id_to_path = id_to_path
        self.current_path = current_path
        self.add_item(FolderUploadSelect(options, cog, user, id_to_path, current_path))


class FolderUploadSelect(discord.ui.Select):
    def __init__(self, options, cog, user, id_to_path, current_path):
        self.cog = cog
        self.user = user
        self.id_to_path = id_to_path
        self.current_path = current_path
        super().__init__(placeholder="Choisis un dossier", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Tu ne peux pas utiliser ce menu.", ephemeral=True)
            return

        selected_id = self.values[0]
        selected_path = self.id_to_path[selected_id]

        if selected_id == "back":
            await self.cog.show_folder(interaction, selected_path)
        else:
            await interaction.response.send_message(
                f"📥 Envoie maintenant un fichier à ajouter ou remplacer dans `{selected_path}` (dans les 60 secondes).",
                ephemeral=True
            )

            def check(m):
                return m.author.id == interaction.user.id and m.attachments and isinstance(m.channel, discord.abc.Messageable)

            try:
                message = await self.cog.bot.wait_for("message", check=check, timeout=60)
                attachment = message.attachments[0]
                await self.cog.upload_file_to_repo(interaction, selected_path, attachment)
            except Exception as e:
                await interaction.followup.send("⏱️ Temps écoulé ou erreur. Annulation de l’opération.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(EditRepo(bot))
