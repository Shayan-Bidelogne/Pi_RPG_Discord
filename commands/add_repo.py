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


class EditRepo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.upload_sessions = {}  # user_id -> UploadSession

    @app_commands.command(name="edit_repo", description="Browse and upload files to GitHub repo")
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
                    await interaction.response.send_message("❌ Cannot access the GitHub repository.", ephemeral=True)
                    return
                data = await resp.json()

        # Separate folders and files
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

        view = EditRepoView(options, self, interaction.user, id_to_item, path)

        if interaction.response.is_done():
            await interaction.edit_original_response(content=None, view=view)
        else:
            await interaction.response.send_message(content=None, view=view, ephemeral=True)


class EditRepoView(discord.ui.View):
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

        # Remove old select if exists
        for child in self.children:
            if isinstance(child, EditRepoSelect):
                self.remove_item(child)
                break

        self.clear_items()  # Clear all items before adding new ones

        self.add_item(EditRepoSelect(page_options, self.cog, self.user, self.id_to_item, self.current_path))

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


class EditRepoSelect(discord.ui.Select):
    def __init__(self, options, cog, user, id_to_item, current_path):
        self.cog = cog
        self.user = user
        self.id_to_item = id_to_item
        self.current_path = current_path
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

        else:
            # If user selected a folder (for upload) => invite to upload file
            # We won't get here because folder handled above

            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # To prevent other users messing with the menu
        return interaction.user.id == self.user.id


class UploadConfirmView(discord.ui.View):
    def __init__(self, cog, user, full_path, attachment):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.full_path = full_path
        self.attachment = attachment
        self.value = None

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Ce bouton n'est pas pour toi.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        file_bytes = await self.attachment.read()

        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{self.full_path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Check if file exists to get sha (for update)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                sha = data.get("sha") if resp.status == 200 else None

            payload = {
                "message": f"Upload file {self.attachment.filename}",
                "content": base64.b64encode(file_bytes).decode("utf-8"),
            }
            if sha:
                payload["sha"] = sha

            async with session.put(url, headers=headers, json=payload) as resp_put:
                if resp_put.status in (200, 201):
                    await interaction.followup.send(f"✅ Fichier **{self.attachment.filename}** ajouté/remplacé dans `{self.full_path.rsplit('/',1)[0]}`.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Erreur lors de l’upload sur GitHub.", ephemeral=True)

        self.value = True
        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Ce bouton n'est pas pour toi.", ephemeral=True)
            return

        await interaction.response.send_message("❌ Upload annulé.", ephemeral=True)
        self.value = False
        self.stop()


class UploadListener(discord.ui.View):
    def __init__(self, cog, user, folder_path):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.folder_path = folder_path
        self.file_attachment = None
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def wait_for_upload(self, interaction: discord.Interaction):
        """Attente d’un message avec un fichier attaché envoyé par l’utilisateur dans le même canal."""
        await interaction.followup.send(f"➡️ Envoie un fichier (pièce jointe) à uploader dans `{self.folder_path}`.", ephemeral=True)

        def check(m: discord.Message):
            return (
                m.author.id == self.user.id
                and m.channel.id == interaction.channel.id
                and len(m.attachments) == 1
            )

        try:
            message = await self.cog.bot.wait_for("message", timeout=120.0, check=check)
            self.file_attachment = message.attachments[0]
            self.message = message
            return True
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Temps écoulé, upload annulé.", ephemeral=True)
            return False


class EditRepoView(EditRepoView):  # On override pour ajouter le nouveau comportement sur dossier
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id

    async def on_timeout(self):
        # Timeout possible à gérer si besoin
        pass

    async def on_error(self, error, item, interaction):
        await interaction.response.send_message("❌ Une erreur est survenue.", ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Limit interaction aux utilisateurs qui ont lancé la commande
        return interaction.user.id == self.user.id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Prevent others from interacting
        return interaction.user.id == self.user.id

    async def on_select_callback(self, interaction: discord.Interaction, selected_id):
        # Deprecated, but you get the idea
        pass

    async def _process_selection(self, interaction: discord.Interaction, selected_id: str):
        item = self.id_to_item.get(selected_id)
        if not item:
            await interaction.response.send_message("❌ Invalid selection.", ephemeral=True)
            return

        if item['type'] == "dir":
            # Instead of navigating immediately, we propose upload or navigation

            # Invite user to either navigate or upload in this folder
            # For simplicity, on folder selection, propose two buttons: "Open folder" and "Upload file"

            view = FolderChoiceView(self.cog, self.user, item['path'])
            await interaction.response.edit_message(content=f"📂 Dossier `{item['path']}` sélectionné. Que voulez-vous faire ?", view=view)

        elif item['type'] == "file":
            # Download and send the file as before
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
            await interaction.response.send_message(f"Voici le fichier **{item['name']}** :", file=file, ephemeral=True)


class FolderChoiceView(discord.ui.View):
    def __init__(self, cog, user, folder_path):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.folder_path = folder_path

    @discord.ui.button(label="Ouvrir le dossier", style=discord.ButtonStyle.primary)
    async def open_folder(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Ce bouton n'est pas pour toi.", ephemeral=True)
            return

        await self.cog.show_folder(interaction, self.folder_path)
        self.stop()

    @discord.ui.button(label="Uploader un fichier ici", style=discord.ButtonStyle.success)
    async def upload_file(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Ce bouton n'est pas pour toi.", ephemeral=True)
            return

        # Start upload listener
        upload_listener = UploadListener(self.cog, self.user, self.folder_path)
        await upload_listener.wait_for_upload(interaction)
        if not upload_listener.file_attachment:
            # Already handled timeout message
            self.stop()
            return

        # Ask confirmation
        confirm_view = UploadConfirmView(self.cog, self.user, f"{self.folder_path}/{upload_listener.file_attachment.filename}" if self.folder_path else upload_listener.file_attachment.filename, upload_listener.file_attachment)
        await interaction.followup.send(
            content=(
                f"⚠️ Confirmation d’upload :\n"
                f"- Chemin : `{confirm_view.full_path}`\n"
                f"- Fichier : `{upload_listener.file_attachment.filename}`\n"
                "Cliquez sur **Confirmer** pour valider ou **Annuler** pour abandonner."
            ),
            view=confirm_view,
            ephemeral=True
        )

        await confirm_view.wait()
        self.stop()


async def setup(bot):
    await bot.add_cog(EditRepo(bot))
