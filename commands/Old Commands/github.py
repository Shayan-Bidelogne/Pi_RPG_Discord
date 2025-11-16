import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import io
from dotenv import load_dotenv

if os.path.exists(".env"):
    load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = os.getenv("REPO_OWNER") or "Shayan-Bidelogne"
REPO_NAME = os.getenv("REPO_NAME") or "Pi_RPG"

class GithubBrowse(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="github", description="Browse and download files from GitHub repo")
    @app_commands.checks.has_role("admin")
    async def github(self, interaction: discord.Interaction):
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
                    await interaction.response.send_message("❌ Cannot access the GitHub repository.", ephemeral=True)
                    return
                data = await resp.json()

        files = [item for item in data if item['type'] == "file"]
        dirs = [item for item in data if item['type'] == "dir"]

        id_to_item = {}
        options = []

        for i, dir in enumerate(dirs):
            key = f"d{i}"
            id_to_item[key] = {"type": "dir", "path": dir['path']}
            options.append(discord.SelectOption(label=dir['name'], value=key, description="📁 Folder"))

        for i, file in enumerate(files):
            key = f"f{i}"
            id_to_item[key] = {"type": "file", "path": file['path'], "name": file['name']}
            options.append(discord.SelectOption(label=file['name'], value=key, description="📄 File"))

        if path:
            parent = "/".join(path.split("/")[:-1])
            id_to_item["back"] = {"type": "dir", "path": parent or ""}
            options.append(discord.SelectOption(label="🔙 Back", value="back", description="Go back"))

        view = GithubBrowseView(options, self, interaction.user, id_to_item, path)

        if interaction.response.is_done():
            await interaction.edit_original_response(content=None, view=view)
        else:
            await interaction.response.send_message(content=None, view=view, ephemeral=True)

class GithubBrowseView(discord.ui.View):
    def __init__(self, options, cog, user, id_to_item, current_path, page=0):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user
        self.id_to_item = id_to_item
        self.options = options
        self.current_path = current_path
        self.page = page
        self.max_per_page = 25
        self.update_select()

    def update_select(self):
        start = self.page * self.max_per_page
        end = start + self.max_per_page
        page_options = self.options[start:end]

        self.clear_items()
        self.add_item(GithubBrowseSelect(page_options, self.cog, self.user, self.id_to_item, self.current_path))

        if self.page > 0:
            self.add_item(discord.ui.Button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev"))
        if end < len(self.options):
            self.add_item(discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next"))

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You cannot use this button.", ephemeral=True)
            return
        self.page = max(self.page - 1, 0)
        self.update_select()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You cannot use this button.", ephemeral=True)
            return
        self.page += 1
        self.update_select()
        await interaction.response.edit_message(view=self)

class GithubBrowseSelect(discord.ui.Select):
    def __init__(self, options, cog, user, id_to_item, current_path):
        super().__init__(placeholder="Choose a folder or a file", options=options, max_values=1, min_values=1)
        self.cog = cog
        self.user = user
        self.id_to_item = id_to_item
        self.current_path = current_path

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You cannot use this menu.", ephemeral=True)
            return

        selected_id = self.values[0]
        item = self.id_to_item.get(selected_id)
        if not item:
            await interaction.response.send_message("❌ Invalid selection.", ephemeral=True)
            return

        if item['type'] == "dir":
            await self.cog.show_folder(interaction, item['path'])
        elif item['type'] == "file":
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{item['path']}"
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3.raw"
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        await interaction.response.send_message("❌ Cannot retrieve the file.", ephemeral=True)
                        return
                    file_bytes = await resp.read()

            file = discord.File(fp=io.BytesIO(file_bytes), filename=item['name'])
            await interaction.response.send_message(f"Here is the file **{item['name']}**:", file=file, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GithubBrowse(bot))
