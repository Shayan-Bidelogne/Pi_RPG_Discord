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

        id_to_item = {}
        options = []

        for i, item in enumerate(data):
            key = f"item{i}"
            id_to_item[key] = item
            label = item['name']
            if item['type'] == 'dir':
                label = f"📁 {label}"
            else:
                label = f"📄 {label}"
            options.append(discord.SelectOption(label=label, value=key))

        if path:
            parent = "/".join(path.split("/")[:-1])
            id_to_item["back"] = {"type": "back", "path": parent or ""}
            options.append(discord.SelectOption(label="🔙 Retour", value="back"))

        view = FolderEditView(options, self, interaction.user, id_to_item, path)

        if interaction.response.is_done():
            await interaction.edit_original_response(content="📂 Choisis un fichier ou un dossier :", view=view)
        else:
            await interaction.response.send_message(content="📂 Choisis un fichier ou un dossier :", view=view, ephemeral=True)


class FolderEditView(discord.ui.View):
    def __init__(self, options, cog, user, id_to_item, current_path):
        super().__init__(timeout=120)
        self.add_item(FolderEditSelect(options, cog, user, id_to_item, current_path))


class FolderEditSelect(discord.ui.Select):
    def __init__(self, options, cog, user, id_to_item, current_path):
        self.cog = cog
        self.user = user
        self.id_to_item = id_to_item
        self.current_path = current_path
        super().__init__(placeholder="Choisis un fichier ou un dossier", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Tu ne peux pas utiliser ce menu.", ephemeral=True)
            return

        selected_id = self.values[0]
        item = self.id_to_item[selected_id]

        if selected_id == "back":
            await self.cog.show_folder(interaction, item['path'])
        elif item['type'] == "dir":
            await self.cog.show_folder(interaction, item['path'])
        elif item['type'] == "file":
            # Modifier un fichier
            url = item['url']
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    data = await resp.json()
                    content = base64.b64decode(data['content']).decode()
                    sha = data['sha']
                    await interaction.response.send_modal(FileContentModal(self.cog, item['path'], self.user, content, sha))


class FileContentModal(discord.ui.Modal, title="Contenu du fichier"):
    def __init__(self, cog, full_path, user, default_content="", sha=None):
        super().__init__()
        self.cog = cog
        self.full_path = full_path
        self.user = user
        self.sha = sha
        self.content = discord.ui.TextInput(label="Contenu", style=discord.TextStyle.paragraph, required=True, default=default_content)
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        payload = {
            "message": f"Mise à jour de {self.full_path}",
            "content": base64.b64encode(self.content.value.encode()).decode("utf-8")
        }
        if self.sha:
            payload["sha"] = self.sha

        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{self.full_path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status in (200, 201):
                    await interaction.response.send_message(f"✅ Fichier **{self.full_path}** mis à jour avec succès.", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Erreur lors de la mise à jour du fichier.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(EditRepo(bot))
