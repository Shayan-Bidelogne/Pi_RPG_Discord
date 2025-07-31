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

    @app_commands.command(name="browse_repo", description="Browse folders of the private GitHub repo")
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
                    await interaction.response.send_message("❌ Cannot access the GitHub repository.", ephemeral=True)
                    return
                data = await resp.json()

        # Separate folders and files
        files = [item for item in data if item['type'] == "file"]
        dirs = [item for item in data if item['type'] == "dir"]

        # Prepare dropdown menu with folders + files + back option
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

        view = FolderSelectView(options, self, interaction.user, id_to_item)

        if interaction.response.is_done():
            await interaction.edit_original_response(content=None, view=view)
        else:
            await interaction.response.send_message(content=None, view=view, ephemeral=True)


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

        # Clear buttons + selects then add select and pagination buttons if needed
        self.clear_items()
        self.add_item(FolderSelect(page_options, self.cog, self.user, self.id_to_path))

        if self.page > 0:
            self.add_item(discord.ui.Button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev"))
        if end < len(self.all_options):
            self.add_item(discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next"))

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You cannot use this button.", ephemeral=True)
            return
        if self.page > 0:
            self.page -= 1
            self.update_select()
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You cannot use this button.", ephemeral=True)
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
        super().__init__(placeholder="Choose a folder or a file", options=options, max_values=1, min_values=1)

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
            # Navigate into the selected folder
            await self.cog.show_folder(interaction, item['path'])

        elif item['type'] == "file":
            # Download the file and send it as attachment
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{item['path']}"
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3.raw"  # Raw content
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
    await bot.add_cog(BrowseRepo(bot))
