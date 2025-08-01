import discord
from discord.ext import commands

class Recruitment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1400511222394126367  # Remplace avec l'ID du canal de lancement
        self.role_channel_map = {
            "pixelart": 1355852568806293637,
            "dev": 1363812990566006865,
            "marketing": 333333333333333333
        }
        self.user_roles = {}  # Pour mémoriser le rôle sélectionné par l'utilisateur

    async def setup(self):
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            embed = discord.Embed(
                title="🚀 Recrutement ouvert !",
                description="Clique sur **Postuler** pour démarrer ta candidature.",
                color=discord.Color.blurple()
            )
            await channel.send(embed=embed, view=ApplyButtonView(self))

class ApplyButtonView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Postuler", style=discord.ButtonStyle.primary)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")

        channel = await guild.create_text_channel(f"ticket-{user.name}", overwrites=overwrites, category=category)
        await channel.send(f"{user.mention}, quel rôle vous intéresse ?", view=RoleChoiceView(self.cog, user))

class RoleChoiceView(discord.ui.View):
    def __init__(self, cog, user):
        super().__init__(timeout=None)
        self.cog = cog
        self.user = user

    @discord.ui.select(
        placeholder="Quel rôle vous intéresse ?",
        options=[
            discord.SelectOption(label="Pixel Art", value="pixelart"),
            discord.SelectOption(label="Développement", value="dev"),
            discord.SelectOption(label="Marketing", value="marketing")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        role = select.values[0]
        self.cog.user_roles[self.user.id] = role
        file = discord.File(f"assets/recrutement_{role}.pdf")
        await interaction.response.send_message(f"Voici le document pour le rôle **{role}** :", file=file)
        await interaction.followup.send("Souhaites-tu poursuivre et choisir une tâche ?", view=ContinueView(self.cog, self.user))

class ContinueView(discord.ui.View):
    def __init__(self, cog, user):
        super().__init__(timeout=None)
        self.cog = cog
        self.user = user

    @discord.ui.button(label="Oui, je veux voir les tâches", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = self.cog.user_roles.get(self.user.id)
        task_channel_id = self.cog.role_channel_map.get(role)
        channel = interaction.guild.get_channel(task_channel_id)

        if not channel:
            await interaction.response.send_message("Aucun salon de tâches trouvé.", ephemeral=True)
            return

        messages = [msg async for msg in channel.history(limit=20) if not msg.author.bot]
        if not messages:
            await interaction.response.send_message("Aucune tâche disponible pour l’instant.", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=msg.content[:80], value=str(msg.id))
            for msg in messages[:25]  # Limite Discord: max 25 options
        ]

        view = TaskChoiceView(options)
        await interaction.response.send_message("Voici les tâches disponibles :", view=view, ephemeral=True)

class TaskChoiceView(discord.ui.View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.add_item(TaskSelect(options))

class TaskSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choisis une tâche :", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        task_id = self.values[0]
        await interaction.response.send_message(f"Utilise `/assign_task {task_id}` pour t’assigner cette tâche.", ephemeral=True)

# Pour setup
async def setup(bot):
    cog = Recruitment(bot)
    await bot.add_cog(cog)
    await cog.setup()
