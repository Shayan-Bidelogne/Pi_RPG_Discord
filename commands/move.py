import discord
from discord import app_commands
from discord.ext import commands
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.errors import HttpError

# Paramètres
SOURCE_FOLDER_ID = "1RAOczLrtnsSzEQHOzV3ZyUnJS0iroF7R"
DEST_ROOT_FOLDER_ID = "1AA-hk-fwkdkzKroc4GsgitHmoWMcVuZ9"
SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "credentials.json"

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=credentials)


def list_files_in_folder(folder_id):
    results = drive_service.files().list(
        q=f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)"
    ).execute()
    return results.get("files", [])


def get_subfolders(parent_id, prefix=""):
    folders = []
    results = drive_service.files().list(
        q=f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed = false",
        fields="files(id, name)"
    ).execute()

    for folder in results.get("files", []):
        folders.append((folder["id"], f"{prefix}{folder['name']}"))
        folders.extend(get_subfolders(folder["id"], prefix + "📁 "))
    return folders


class RenameModal(discord.ui.Modal, title="Renommer le fichier"):
    def __init__(self, file_id, old_name):
        super().__init__()
        self.file_id = file_id
        self.old_name = old_name

        self.new_name = discord.ui.TextInput(
            label="Nouveau nom de fichier",
            placeholder="ex: nouveau_nom.pdf",
            default=old_name,
            required=True
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            drive_service.files().update(
                fileId=self.file_id,
                body={"name": self.new_name.value}
            ).execute()

            await interaction.response.edit_message(
                content=f"✅ Le fichier a été renommé en **{self.new_name.value}**.",
                view=None
            )
        except HttpError as e:
            await interaction.response.edit_message(
                content=f"❌ Erreur lors du renommage du fichier : {e}",
                view=None
            )


class RenamePrompt(discord.ui.View):
    def __init__(self, file_id, old_name):
        super().__init__(timeout=30)
        self.file_id = file_id
        self.old_name = old_name

    @discord.ui.button(label="Renommer le fichier", style=discord.ButtonStyle.primary)
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RenameModal(self.file_id, self.old_name))


class FolderSelect(discord.ui.View):
    def __init__(self, file_id, file_name, folders):
        super().__init__(timeout=60)
        self.file_id = file_id
        self.file_name = file_name

        options = [
            discord.SelectOption(label=name[:100], value=fid)
            for fid, name in folders
        ]
        self.select = discord.ui.Select(placeholder="Choisis un dossier de destination", options=options)
        self.select.callback = self.move_file_callback
        self.add_item(self.select)

    async def move_file_callback(self, interaction: discord.Interaction):
        target_folder_id = self.select.values[0]

        try:
            file = drive_service.files().get(fileId=self.file_id, fields="parents").execute()
            previous_parents = ",".join(file.get("parents", []))

            drive_service.files().update(
                fileId=self.file_id,
                addParents=target_folder_id,
                removeParents=previous_parents,
                fields="id, parents"
            ).execute()

            await interaction.response.edit_message(
                content=f"✅ Le fichier **{self.file_name}** a bien été déplacé dans le dossier sélectionné.",
                view=None
            )

            await interaction.followup.send(
                content="🔤 Souhaites-tu renommer ce fichier ?",
                view=RenamePrompt(self.file_id, self.file_name),
                ephemeral=True
            )

        except HttpError as e:
            await interaction.response.edit_message(
                content=f"❌ Erreur lors du déplacement du fichier : {e}",
                view=None
            )


class FileSelect(discord.ui.View):
    def __init__(self, files, folders):
        super().__init__(timeout=60)
        self.folders = folders

        options = [
            discord.SelectOption(label=file["name"][:100], value=f'{file["id"]}:{file["name"]}')
            for file in files
        ]
        self.select = discord.ui.Select(placeholder="Choisis un fichier à déplacer", options=options)
        self.select.callback = self.file_chosen
        self.add_item(self.select)

    async def file_chosen(self, interaction: discord.Interaction):
        file_id, file_name = self.select.values[0].split(":", 1)

        await interaction.response.edit_message(
            content=f"📁 Où veux-tu déplacer **{file_name}** ?",
            view=FolderSelect(file_id, file_name, self.folders)
        )


@discord.app_commands.checks.has_permissions(administrator=True)
@discord.app_commands.command(name="move", description="Déplace un fichier vers un sous-dossier.")
async def move(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    files = list_files_in_folder(SOURCE_FOLDER_ID)
    if not files:
        await interaction.followup.send("❌ Aucun fichier trouvé dans le dossier source.", ephemeral=True)
        return

    folders = get_subfolders(DEST_ROOT_FOLDER_ID)
    if not folders:
        await interaction.followup.send("❌ Aucun dossier de destination trouvé.", ephemeral=True)
        return

    await interaction.followup.send(
        "📄 Quel fichier veux-tu déplacer ?",
        view=FileSelect(files, folders),
        ephemeral=True
    )


# Setup du bot
async def setup(bot: commands.Bot):
    bot.tree.add_command(move)
