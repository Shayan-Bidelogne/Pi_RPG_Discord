from discord import ui, app_commands, Interaction
from discord.ext import commands
import aiohttp
import io

class EditRepo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending_edits = {}  # user_id : {mode: "add"|"edit", path: folder_path, filename: str, content: str}

    @app_commands.command(name="edit_repo", description="Add or edit files in the private GitHub repo")
    async def edit_repo(self, interaction: Interaction):
        # Ask user: add or edit?
        options = [
            discord.SelectOption(label="Add a file", value="add", description="Add a new file"),
            discord.SelectOption(label="Edit a file", value="edit", description="Modify an existing file")
        ]
        view = ModeSelectView(options, self, interaction.user)
        await interaction.response.send_message("Choose mode:", view=view, ephemeral=True)

class ModeSelectView(ui.View):
    def __init__(self, options, cog, user):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.options = options
        self.add_item(ModeSelect(options, cog, user))

class ModeSelect(ui.Select):
    def __init__(self, options, cog, user):
        super().__init__(placeholder="Select mode", options=options, max_values=1, min_values=1)
        self.cog = cog
        self.user = user

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("You can't use this menu.", ephemeral=True)
            return

        mode = self.values[0]
        # Store user state
        self.cog.pending_edits[self.user.id] = {"mode": mode, "path": "", "filename": None, "content": None}
        # Start folder navigation to select target folder
        await self.cog.show_folder_edit(interaction, "")

# Now we add show_folder_edit in EditRepo class for folder navigation (similar to show_folder but only folders, no files)

async def show_folder_edit(self, interaction: Interaction, path: str):
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

    # Keep only folders
    dirs = [item for item in data if item['type'] == "dir"]

    # Add back option if not root
    options = []
    id_to_path = {}

    for i, dir in enumerate(dirs):
        key = f"d{i}"
        id_to_path[key] = dir['path']
        options.append(discord.SelectOption(label=dir['name'], value=key, description="📁 Folder"))

    if path:
        parent = "/".join(path.split("/")[:-1])
        id_to_path["back"] = parent or ""
        options.append(discord.SelectOption(label="🔙 Back", value="back", description="Go back"))

    view = FolderEditSelectView(options, self, interaction.user, id_to_path)

    if interaction.response.is_done():
        await interaction.edit_original_response(content=f"Select a folder to {self.pending_edits[interaction.user.id]['mode']}.", view=view)
    else:
        await interaction.response.send_message(f"Select a folder to {self.pending_edits[interaction.user.id]['mode']}.", view=view, ephemeral=True)


EditRepo.show_folder_edit = show_folder_edit

class FolderEditSelectView(ui.View):
    def __init__(self, options, cog, user, id_to_path, page=0):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.id_to_path = id_to_path
        self.options = options
        self.page = page
        self.max_per_page = 25
        self.update_select()

    def update_select(self):
        start = self.page * self.max_per_page
        end = start + self.max_per_page
        page_options = self.options[start:end]

        # Remove old select if exists
        for child in self.children:
            if isinstance(child, FolderEditSelect):
                self.remove_item(child)
                break

        self.clear_items()
        self.add_item(FolderEditSelect(page_options, self.cog, self.user, self.id_to_path))

        if self.page > 0:
            self.add_item(discord.ui.Button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev_edit"))
        if end < len(self.options):
            self.add_item(discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next_edit"))

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev_edit")
    async def prev_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this button.", ephemeral=True)
            return
        if self.page > 0:
            self.page -= 1
            self.update_select()
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next_edit")
    async def next_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this button.", ephemeral=True)
            return
        if (self.page + 1) * self.max_per_page < len(self.options):
            self.page += 1
            self.update_select()
            await interaction.response.edit_message(view=self)

class FolderEditSelect(ui.Select):
    def __init__(self, options, cog, user, id_to_path):
        super().__init__(placeholder="Select folder", options=options, max_values=1, min_values=1)
        self.cog = cog
        self.user = user
        self.id_to_path = id_to_path

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this menu.", ephemeral=True)
            return
        selected = self.values[0]
        if selected == "back":
            new_path = self.id_to_path[selected]
            await self.cog.show_folder_edit(interaction, new_path)
            return
        folder_path = self.id_to_path.get(selected)
        if not folder_path:
            await interaction.response.send_message("❌ Invalid selection.", ephemeral=True)
            return

        user_state = self.cog.pending_edits[self.user.id]
        user_state["path"] = folder_path

        if user_state["mode"] == "add":
            # Ask user for new filename via modal
            modal = FilenameModal(self.cog, self.user)
            await interaction.response.send_modal(modal)
        else:
            # For editing, show files in this folder to select one (we will do next)
            await self.cog.show_files_edit(interaction, folder_path)

class FilenameModal(ui.Modal, title="Enter filename"):
    def __init__(self, cog, user):
        super().__init__()
        self.cog = cog
        self.user = user
        self.filename = ui.TextInput(label="Filename (with extension)", placeholder="example.txt", required=True)
        self.add_item(self.filename)

    async def on_submit(self, interaction: Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this modal.", ephemeral=True)
            return
        filename = self.filename.value.strip()
        if not filename:
            await interaction.response.send_message("❌ Filename cannot be empty.", ephemeral=True)
            return

        user_state = self.cog.pending_edits[self.user.id]
        user_state["filename"] = filename

        # Ask for file content (next step)
        await self.cog.ask_file_content(interaction)


import base64

class EditRepo(commands.Cog):
    # ... (garde tout ce qui précède)

    async def show_files_edit(self, interaction: Interaction, folder_path: str):
        """Affiche les fichiers dans le dossier pour choisir lequel éditer"""
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{folder_path}"
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
        if not files:
            await interaction.response.send_message("📁 No files found in this folder.", ephemeral=True)
            return

        options = []
        id_to_file = {}
        for i, file in enumerate(files):
            key = f"f{i}"
            id_to_file[key] = file
            options.append(discord.SelectOption(label=file['name'], value=key, description="📄 File"))

        view = FileEditSelectView(options, self, interaction.user, id_to_file)

        if interaction.response.is_done():
            await interaction.edit_original_response(content="Select a file to edit:", view=view)
        else:
            await interaction.response.send_message("Select a file to edit:", view=view, ephemeral=True)

    async def ask_file_content(self, interaction: Interaction):
        """Demande à l’utilisateur de saisir le contenu du fichier (modal)"""
        modal = FileContentModal(self, interaction.user)
        await interaction.response.send_modal(modal)

    async def confirm_edit(self, interaction: Interaction):
        """Affiche un récapitulatif avant envoi sur GitHub"""
        user_state = self.pending_edits.get(interaction.user.id)
        if not user_state:
            await interaction.response.send_message("❌ No pending edit found.", ephemeral=True)
            return

        mode = user_state["mode"]
        path = user_state["path"]
        filename = user_state["filename"]
        content = user_state["content"]

        if not all([mode, path, filename, content is not None]):
            await interaction.response.send_message("❌ Missing data for confirmation.", ephemeral=True)
            return

        full_path = f"{path}/{filename}" if path else filename
        summary = (
            f"**Mode:** {'Add' if mode == 'add' else 'Edit'}\n"
            f"**Path:** `{full_path}`\n"
            f"**Content preview:**\n```diff\n{content[:500]}\n```"
        )

        view = ConfirmEditView(self, interaction.user)
        await interaction.response.send_message(f"Please confirm your changes:\n\n{summary}", view=view, ephemeral=True)

    async def send_to_github(self, interaction: Interaction):
        """Envoi le fichier sur GitHub (création ou mise à jour)"""
        user_state = self.pending_edits.get(interaction.user.id)
        if not user_state:
            await interaction.response.send_message("❌ No pending edit found.", ephemeral=True)
            return

        mode = user_state["mode"]
        path = user_state["path"]
        filename = user_state["filename"]
        content = user_state["content"]

        full_path = f"{path}/{filename}" if path else filename

        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{full_path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Need to get SHA if editing an existing file
        sha = None
        if mode == "edit":
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        sha = data.get("sha")
                    else:
                        await interaction.response.send_message("❌ Cannot find the file to edit on GitHub.", ephemeral=True)
                        return

        payload = {
            "message": f"{'Add' if mode == 'add' else 'Edit'} file {full_path} via Discord bot",
            "content": base64.b64encode(content.encode()).decode(),
        }
        if sha:
            payload["sha"] = sha

        async with aiohttp.ClientSession() as session:
            async with session.put(url, headers=headers, json=payload) as resp:
                if resp.status in (200, 201):
                    await interaction.response.send_message(f"✅ File `{full_path}` successfully {'added' if mode=='add' else 'updated'}.", ephemeral=True)
                    # Clear pending state
                    self.pending_edits.pop(interaction.user.id, None)
                else:
                    text = await resp.text()
                    await interaction.response.send_message(f"❌ Failed to update file on GitHub.\nResponse: {resp.status}\n{text}", ephemeral=True)


class FileEditSelectView(ui.View):
    def __init__(self, options, cog, user, id_to_file, page=0):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.id_to_file = id_to_file
        self.options = options
        self.page = page
        self.max_per_page = 25
        self.update_select()

    def update_select(self):
        start = self.page * self.max_per_page
        end = start + self.max_per_page
        page_options = self.options[start:end]

        for child in self.children:
            if isinstance(child, FileEditSelect):
                self.remove_item(child)
                break

        self.clear_items()
        self.add_item(FileEditSelect(page_options, self.cog, self.user, self.id_to_file))

        if self.page > 0:
            self.add_item(discord.ui.Button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev_files"))
        if end < len(self.options):
            self.add_item(discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next_files"))

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="prev_files")
    async def prev_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this button.", ephemeral=True)
            return
        if self.page > 0:
            self.page -= 1
            self.update_select()
            await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next_files")
    async def next_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this button.", ephemeral=True)
            return
        if (self.page + 1) * self.max_per_page < len(self.options):
            self.page += 1
            self.update_select()
            await interaction.response.edit_message(view=self)

class FileEditSelect(ui.Select):
    def __init__(self, options, cog, user, id_to_file):
        super().__init__(placeholder="Select file to edit", options=options, max_values=1, min_values=1)
        self.cog = cog
        self.user = user
        self.id_to_file = id_to_file

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this menu.", ephemeral=True)
            return

        selected = self.values[0]
        file = self.id_to_file.get(selected)
        if not file:
            await interaction.response.send_message("❌ Invalid selection.", ephemeral=True)
            return

        # Save filename in state
        user_state = self.cog.pending_edits[self.user.id]
        user_state["filename"] = file['name']

        # Fetch current content from GitHub (raw)
        url = file['url']
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.raw"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    await interaction.response.send_message("❌ Cannot fetch file content.", ephemeral=True)
                    return
                file_bytes = await resp.read()
                content = file_bytes.decode(errors='replace')

        user_state["content"] = content
        # Ask user to edit content via modal
        await self.cog.ask_file_content(interaction)


class FileContentModal(ui.Modal, title="Edit file content"):
    def __init__(self, cog, user):
        super().__init__()
        self.cog = cog
        self.user = user
        self.content_input = ui.TextInput(label="File content (Markdown supported)", style=discord.TextStyle.paragraph, required=True, min_length=1, max_length=6000)
        self.add_item(self.content_input)

    async def on_submit(self, interaction: Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this modal.", ephemeral=True)
            return

        content = self.content_input.value
        user_state = self.cog.pending_edits.get(self.user.id)
        if not user_state:
            await interaction.response.send_message("❌ No pending edit found.", ephemeral=True)
            return

        user_state["content"] = content
        # Show confirmation
        await self.cog.confirm_edit(interaction)


class ConfirmEditView(ui.View):
    def __init__(self, cog, user):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this button.", ephemeral=True)
            return
        await self.cog.send_to_github(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 You can't use this button.", ephemeral=True)
            return
        await interaction.response.send_message("Operation cancelled.", ephemeral=True)
        self.cog.pending_edits.pop(self.user.id, None)
        self.stop()

async def setup(bot):
    await bot.add_cog(EditRepo(bot))
