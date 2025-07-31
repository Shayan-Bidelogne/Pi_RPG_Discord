import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv
import io
import base64
import asyncio

if os.path.exists(".env"):
    load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = os.getenv("REPO_OWNER") or "Shayan-Bidelogne"
REPO_NAME = os.getenv("REPO_NAME") or "Pi_RPG"


class GithubAdd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="github_add", description="Browse and upload files to GitHub repo")
    async def github_add(self, interaction: discord.Interaction):
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
            options.append(discord.SelectOption(label=dir['name'], value=key, description="\ud83d\udcc1 Folder"))

        for i, file in enumerate(files):
            key = f"f{i}"
            id_to_item[key] = {"type": "file", "path": file['path'], "name": file['name']}
            options.append(discord.SelectOption(label=file['name'], value=key, description="\ud83d\udcc4 File"))

        if path:
            parent = "/".join(path.split("/")[:-1])
            id_to_item["back"] = {"type": "dir", "path": parent or ""}
            options.append(discord.SelectOption(label="\ud83d\udd19 Back", value="back", description="Go back"))

        view = GithubAddView(options, self, interaction.user, id_to_item, path)

        if interaction.response.is_done():
            await interaction.edit_original_response(content=None, view=view)
        else:
            await interaction.response.send_message(content=None, view=view, ephemeral=True)


class GithubAddView(discord.ui.View):
    def __init__(self, all_options, cog, user, id_to_item, current_path, page=0):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user
        self.id_to_item = id_to_item
        self.all_options = all_options
        self.current_path = current_path
        self.page = page
        self.max_per_page = 25
        self.update_select()

    def update_select(self):
        start = self.page * self.max_per_page
        end = start + self.max_per_page
        page_options = self.all_options[start:end]

        self.clear_items()
        self.add_item(GithubAddSelect(page_options, self.cog, self.user, self.id_to_item, self.current_path))

        buttons = []
        if self.page > 0:
            buttons.append(discord.ui.Button(label="\u2b05\ufe0f Previous", style=discord.ButtonStyle.secondary, custom_id="prev"))
        if end < len(self.all_options):
            buttons.append(discord.ui.Button(label="Next \u27a1\ufe0f", style=discord.ButtonStyle.secondary, custom_id="next"))

        for button in buttons:
            self.add_item(button)

    @discord.ui.button(label="\u2b05\ufe0f Previous", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("\ud83d\udeab You cannot use this button.", ephemeral=True)
            return
        self.page = max(self.page - 1, 0)
        self.update_select()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Next \u27a1\ufe0f", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("\ud83d\udeab You cannot use this button.", ephemeral=True)
            return
        self.page += 1
        self.update_select()
        await interaction.response.edit_message(view=self)


class GithubAddSelect(discord.ui.Select):
    def __init__(self, options, cog, user, id_to_item, current_path):
        self.cog = cog
        self.user = user
        self.id_to_item = id_to_item
        self.current_path = current_path
        super().__init__(placeholder="Choose a folder or a file", options=options, max_values=1, min_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("\ud83d\udeab You cannot use this menu.", ephemeral=True)
            return

        selected_id = self.values[0]
        item = self.id_to_item.get(selected_id)

        if not item:
            await interaction.response.send_message("\u274c Invalid selection.", ephemeral=True)
            return

        if item['type'] == "dir":
            view = FolderChoiceView(self.cog, self.user, item['path'])
            await interaction.response.edit_message(content=f"\ud83d\udcc2 Folder `{item['path']}` selected. What do you want to do?", view=view)
        elif item['type'] == "file":
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{item['path']}"
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3.raw"
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        await interaction.response.send_message("\u274c Cannot retrieve the file.", ephemeral=True)
                        return
                    file_bytes = await resp.read()

            file = discord.File(fp=io.BytesIO(file_bytes), filename=item['name'])
            await interaction.response.send_message(f"Here is the file **{item['name']}**:", file=file, ephemeral=True)


class FolderChoiceView(discord.ui.View):
    def __init__(self, cog, user, folder_path):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.folder_path = folder_path

    @discord.ui.button(label="Open folder", style=discord.ButtonStyle.primary)
    async def open_folder(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("\ud83d\udeab This button is not for you.", ephemeral=True)
            return
        await self.cog.show_folder(interaction, self.folder_path)
        self.stop()

    @discord.ui.button(label="Upload a file here", style=discord.ButtonStyle.success)
    async def upload_file(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("\ud83d\udeab This button is not for you.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        upload_listener = UploadListener(self.cog, self.user, self.folder_path)
        await upload_listener.wait_for_upload(interaction)
        if not upload_listener.file_attachment:
            self.stop()
            return

        full_path = f"{self.folder_path}/{upload_listener.file_attachment.filename}" if self.folder_path else upload_listener.file_attachment.filename
        confirm_view = UploadConfirmView(self.cog, self.user, full_path, upload_listener.file_attachment)
        await interaction.followup.send(
            content=(
                f"\u26a0\ufe0f Upload confirmation:\n"
                f"- Path: `{full_path}`\n"
                f"- File: `{upload_listener.file_attachment.filename}`\n"
                "Click **Confirm** to proceed or **Cancel** to abort."
            ),
            view=confirm_view,
            ephemeral=True
        )
        await confirm_view.wait()
        self.stop()


class UploadListener:
    def __init__(self, cog, user, folder_path):
        self.cog = cog
        self.user = user
        self.folder_path = folder_path
        self.file_attachment = None

    async def wait_for_upload(self, interaction: discord.Interaction):
        channel = interaction.channel or await self.cog.bot.fetch_channel(interaction.channel_id)

        print(f"[UploadListener] Waiting for upload in channel {channel.id}")

        await interaction.followup.send(
            f"\u27a1\ufe0f Please send the file to upload to `{self.folder_path}` in this channel within 2 minutes.",
            ephemeral=True
        )

        def check(m: discord.Message):
            result = (
                m.author.id == self.user.id and
                m.channel.id == channel.id and
                len(m.attachments) == 1
            )
            if result:
                print(f"[UploadListener] File received: {m.attachments[0].filename}")
            return result

        try:
            message = await self.cog.bot.wait_for("message", timeout=120.0, check=check)
            self.file_attachment = message.attachments[0]
        except asyncio.TimeoutError:
            print("[UploadListener] Timeout reached, no file received.")
            await interaction.followup.send("\u23f0 Time is up, upload cancelled.", ephemeral=True)
            self.file_attachment = None


class UploadConfirmView(discord.ui.View):
    def __init__(self, cog, user, path, attachment):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.path = path
        self.attachment = attachment

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("\ud83d\udeab This button is not for you.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        file_bytes = await self.attachment.read()
        content_base64 = base64.b64encode(file_bytes).decode()

        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{self.path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        sha = None
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    sha = data.get("sha")

        payload = {
            "message": f"Add or update file {self.path} via Discord bot",
            "content": content_base64,
        }
        if sha:
            payload["sha"] = sha

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status in (200, 201):
                    await interaction.followup.send(f"\u2705 File `{self.path}` uploaded successfully.", ephemeral=True)
                else:
                    err_text = await resp.text()
                    await interaction.followup.send(f"\u274c Failed to upload file. HTTP {resp.status}: {err_text}", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("\ud83d\udeab This button is not for you.", ephemeral=True)
            return
        await interaction.response.send_message("\u274c Upload cancelled.", ephemeral=True)
        self.stop()


async def setup(bot):
    await bot.add_cog(GithubAdd(bot))