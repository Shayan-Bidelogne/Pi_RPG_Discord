import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv
import io

if os.path.exists(".env"):
    load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = os.getenv("REPO_OWNER") or "Shayan-Bidelogne"
REPO_NAME = os.getenv("REPO_NAME") or "Pi_RPG"

class BrowseRepo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="browse_repo", description="Navigue dans les dossiers du dépôt GitHub privé")
    async def browse_repo(self, interaction: discord.Interaction):
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

        # Séparer dossiers et fichiers
        files = [item for item in data if item['type'] == "file"]
        dirs = [item for item in data if item['type'] == "dir"]

        # Construction du breadcrumb (arborescence affichée)
        breadcrumb = " / ".join(["racine"] + path.split("/")) if path else "racine"

        # Texte affiché (séparation claire dossiers / fichiers)
        content_lines = []
        if dirs:
            content_lines.append("📁 **Dossiers :**")
            for d in dirs:
                content_lines.append(f"  - {d['name']}")
        else:
            content_lines.append("📁 Aucun dossier.")

        if files:
            content_lines.append("\n📄 **Fichiers :**")
            for f in files:
                content_lines.append(f"  - {f['name']}")
        else:
            content_lines.append("\n📄 Aucun fichier.")

        content = "\n".join(content_lines)

        # Préparation du menu déroulant avec dossiers + fichiers + option retour
        id_to_item = {}
        options = []

        for i, dir in enumerate(dirs):
            key = f"d{i}"
            id_to_item[key] = {"type": "dir", "path": dir['path']}
            options.append(discord.SelectOption(label=dir['name'], value=key, description="📁 Dossier"))

        for i, file in enumerate(files):
            key = f"f{i}"
            id_to_item[key] = {"type": "file", "path": file['path'], "name": file['name']}
            options.append(discord.SelectOption(label=file['name'], value=key, description="📄 Fichier"))

        if path:
            parent = "/".join(path.split("/")[:-1])
            id_to_item["back"] = {"type": "dir", "path": parent or ""}
            options.append(discord.SelectOption(label="🔙 Retour", value="back", description="Revenir"))

        view = FolderSelectView(options, self, interaction.user, id_to_item)

        if interaction.response.is_done():
            await interaction.edit_original_response(content=f"**📂 {breadcrumb}**\n\n{content}", view=view)
        else:
            await interaction.response.send_message(f"**📂 {breadcrumb}**\n\n{content}", view=view, ephemeral=True)

class FolderSelectView(discord.ui.View):
    def __init__(self, all_options, cog, user, id_to_path, page=0):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.id_to_path = id_to_path
        self.all_options = all_options
        self.page = page
        self.max_per_page = 25

        self.update_select()

    def update_select(self):
        start = self.page * self.max_per_page
        end = start + self.max_per_page
        page_options = self.all_options[start:end]

        # Remove old select if exists
        for child in self.children:
            if isinstance(child, FolderSelect):
                self.remove_item(child)
                break

        self.add_item(FolderSelect(page_options, self.cog, self.user, self.id_to_path))

        # Add pagination buttons if needed
        self.clear_items()  # clear buttons + selects
        self.add_item(FolderSelect(page_options, self.cog, self.user, self.id_to_path))

        if self.page > 0:
            self.add_item(discord.ui.Button(label="⬅️ Précédent", style=discord.ButtonStyle.secondary, custom_id="prev"))
        if end < len(self.all_options):
            self.add_item(discord.ui.Button(label="Suivant ➡️", style=discord.ButtonStyle.secondary, custom_id="next"))

    @discord.ui.button(label="⬅️ Précédent", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Tu ne peux pas utiliser ce bouton.", ephemeral=True)
            return
        if self.page > 0:
            self.page -= 1
            self.update_select()
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Suivant ➡️", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Tu ne peux pas utiliser ce bouton.", ephemeral=True)
            return
        if (self.page + 1) * self.max_per_page < len(self.all_options):
            self.page += 1
            self.update_select()
            await interaction.response.edit_message(view=self)


class FolderSelect(discord.ui.Select):
    def __init__(self, options, cog, user, id_to_item):
        self.cog = cog
        self.user = user
        self.id_to_item = id_to_item
        super().__init__(placeholder="Choisis un dossier ou un fichier", options=options, max_values=1, min_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Tu ne peux pas utiliser ce menu.", ephemeral=True)
            return

        selected_id = self.values[0]
        item = self.id_to_item.get(selected_id)

        if not item:
            await interaction.response.send_message("❌ Sélection invalide.", ephemeral=True)
            return

        if item['type'] == "dir":
            # Naviguer dans le dossier sélectionné
            await self.cog.show_folder(interaction, item['path'])

        elif item['type'] == "file":
            # Télécharger le fichier et l'envoyer en pièce jointe
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{item['path']}"
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3.raw"  # Contenu brut
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        await interaction.response.send_message("❌ Impossible de récupérer le fichier.", ephemeral=True)
                        return
                    file_bytes = await resp.read()

            file = discord.File(fp=io.BytesIO(file_bytes), filename=item['name'])
            await interaction.response.send_message(f"Voici le fichier **{item['name']}** :", file=file, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BrowseRepo(bot))
