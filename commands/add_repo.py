import os
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import io
import base64
from dotenv import load_dotenv

if os.path.exists(".env"):
    load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = os.getenv("REPO_OWNER") or "Shayan-Bidelogne"
REPO_NAME = os.getenv("REPO_NAME") or "Pi_RPG"

class EditRepo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="edit_repo", description="Ajouter ou modifier un fichier dans le dépôt GitHub")
    async def edit_repo(self, interaction: discord.Interaction):
        await interaction.response.send_message("Que veux-tu faire ?", view=ActionView(self), ephemeral=True)

class ActionView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=120)
        self.cog = cog

    @discord.ui.select(
        placeholder="Ajouter ou modifier un fichier",
        options=[
            discord.SelectOption(label="Ajouter", value="add", description="Ajouter un nouveau fichier"),
            discord.SelectOption(label="Modifier", value="edit", description="Modifier un fichier existant"),
        ]
    )
    async def select_action(self, interaction: discord.Interaction, select: discord.ui.Select):
        action = select.values[0]
        await interaction.response.edit_message(
            content="Choisis un dossier où ajouter/modifier le fichier :", view=None
        )
        await self.cog.show_navigation(interaction, "", action, user=interaction.user)

    async def on_timeout(self):
        self.clear_items()

class FolderNavigationView(discord.ui.View):
    def __init__(self, cog, path, action, user, file_name=None, file_content=None):
        super().__init__(timeout=180)
        self.cog = cog
        self.path = path
        self.user = user
        self.action = action
        self.file_name = file_name
        self.file_content = file_content
        self.options = []
        self.id_to_item = {}

    async def setup(self):
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{self.path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()

        dirs = [item for item in data if item['type'] == "dir"]

        for i, dir in enumerate(dirs):
            key = f"d{i}"
            self.id_to_item[key] = {"type": "dir", "path": dir['path']}
            self.options.append(discord.SelectOption(label=dir['name'], value=key, description="📁 Dossier"))

        if self.path:
            parent = "/".join(self.path.split("/")[:-1])
            self.id_to_item["back"] = {"type": "dir", "path": parent or ""}
            self.options.append(discord.SelectOption(label="🔙 Retour", value="back", description="Revenir en arrière"))

        self.add_item(FolderSelectDropdown(self.options, self))

    async def send(self, interaction, breadcrumb):
        await self.setup()
        await interaction.edit_original_response(content=f"**📂 {breadcrumb}**", view=self)

class FolderSelectDropdown(discord.ui.Select):
    def __init__(self, options, view_obj):
        self.view_obj = view_obj
        super().__init__(placeholder="Choisis un dossier", options=options, max_values=1, min_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_obj.user.id:
            await interaction.response.send_message("🚫 Tu ne peux pas utiliser ce menu.", ephemeral=True)
            return

        selected = self.values[0]
        item = self.view_obj.id_to_item[selected]

        if item['type'] == "dir":
            new_path = item['path']
            breadcrumb = " / ".join(["racine"] + new_path.split("/")) if new_path else "racine"
            await self.view_obj.cog.show_navigation(interaction, new_path, self.view_obj.action, self.view_obj.user, self.view_obj.file_name, self.view_obj.file_content)

class NameModal(discord.ui.Modal, title="Nom du fichier à ajouter"):
    def __init__(self, cog, path, user):
        super().__init__()
        self.cog = cog
        self.path = path
        self.user = user
        self.filename = discord.ui.TextInput(label="Nom du fichier (avec extension)", placeholder="ex: nouveau.py", required=True)
        self.add_item(self.filename)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FileContentModal(self.cog, self.path, self.filename.value, self.user))

class FileContentModal(discord.ui.Modal, title="Contenu du fichier"):
    def __init__(self, cog, path, filename, user):
        super().__init__()
        self.cog = cog
        self.path = path
        self.filename = filename
        self.user = user
        self.content = discord.ui.TextInput(label="Contenu", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        full_path = f"{self.path}/{self.filename}".strip("/")
        await interaction.response.send_message(
            f"✅ Tu es sur le point d’envoyer ce fichier vers **{full_path}**.\nConfirme ?", 
            view=ConfirmSendView(self.cog, full_path, self.content.value, self.user), ephemeral=True
        )

class ConfirmSendView(discord.ui.View):
    def __init__(self, cog, full_path, content, user):
        super().__init__(timeout=60)
        self.cog = cog
        self.path = full_path
        self.content = content
        self.user = user

    @discord.ui.button(label="✅ Confirmer", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Ce bouton n’est pas pour toi.", ephemeral=True)
            return

        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{self.path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        payload = {
            "message": f"Ajout de {self.path}",
            "content": base64.b64encode(self.content.encode()).decode("utf-8")
        }

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status in (200, 201):
                    await interaction.response.edit_message(content="✅ Fichier envoyé sur GitHub avec succès !", view=None)
                else:
                    await interaction.response.edit_message(content="❌ Une erreur est survenue lors de l’envoi.", view=None)

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Opération annulée.", view=None)

# Fonction utilitaire
async def show_navigation(self, interaction, path, action, user, file_name=None, file_content=None):
    breadcrumb = " / ".join(["racine"] + path.split("/")) if path else "racine"
    if action == "add" and not file_name and not file_content:
        await interaction.edit_original_response(content=f"**📂 {breadcrumb}**", view=None)
        await interaction.followup.send_modal(NameModal(self, path, user))
    else:
        view = FolderNavigationView(self, path, action, user, file_name, file_content)
        await view.send(interaction, breadcrumb)

# Attach method dynamically (ou met dans le Cog si tu préfères)
EditRepo.show_navigation = show_navigation

# Obligatoire pour charger l'extension
async def setup(bot):
    await bot.add_cog(EditRepo(bot))
