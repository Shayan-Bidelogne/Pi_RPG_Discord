import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv

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

        files = [f"📄 {item['name']}" for item in data if item['type'] == "file"]
        dirs = [item for item in data if item['type'] == "dir"]

        content = "\n".join(files) if files else "📂 Aucun fichier."

        # Création d'une map id->path pour stocker les chemins complets
        id_to_path = {}
        options = []
        for i, dir in enumerate(dirs):
            key = str(i)  # un simple index en string, toujours <100 chars
            id_to_path[key] = dir['path']
            options.append(discord.SelectOption(label=dir['name'], value=key, description="📁 Dossier"))

        # Option "Retour" avec une valeur fixe (parent folder path)
        if path:
            parent = "/".join(path.split("/")[:-1])
            id_to_path["back"] = parent or ""
            options.append(discord.SelectOption(label="🔙 Retour", value="back", description="Revenir"))

        view = FolderSelectView(options, self, interaction.user, id_to_path)

        if interaction.response.is_done():
            await interaction.edit_original_response(content=f"**📁 {path or 'racine'}**\n\n{content}", view=view)
        else:
            await interaction.response.send_message(f"**📁 {path or 'racine'}**\n\n{content}", view=view, ephemeral=True)


class FolderSelectView(discord.ui.View):
    def __init__(self, options, cog, user, id_to_path):
        super().__init__(timeout=120)
        self.id_to_path = id_to_path
        self.add_item(FolderSelect(options, cog, user, id_to_path))


class FolderSelect(discord.ui.Select):
    def __init__(self, options, cog, user, id_to_path):
        self.cog = cog
        self.user = user
        self.id_to_path = id_to_path
        super().__init__(placeholder="Choisis un dossier", options=options, max_values=1, min_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Tu ne peux pas utiliser ce menu.", ephemeral=True)
            return
        selected_id = self.values[0]
        selected_path = self.id_to_path.get(selected_id, "")
        await self.cog.show_folder(interaction, selected_path)


async def setup(bot):
    await bot.add_cog(BrowseRepo(bot))
