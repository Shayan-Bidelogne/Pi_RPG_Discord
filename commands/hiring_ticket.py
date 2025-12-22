import discord
from discord import app_commands, ui
from discord.ext import commands

# IDs des rôles que l'on peut attribuer/logiquement utiliser
ROLE_IDS = {
    "pixel_artist": 1401139679423631430,
    "dev": 1363812990566006865,
    "marketing": 1401139679423631430,
}

# Pour suivre l'état de l'onboarding par utilisateur (en mémoire pour l'instant)
user_onboarding = {}


class OnboardingView(ui.View):
    def __init__(self, user_id: int, timeout: int | None = 180):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    @ui.button(label="Pixel Artist", style=discord.ButtonStyle.primary, custom_id="role_pixel_artist")
    async def pixel_artist(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_choice(interaction, "pixel_artist")

    @ui.button(label="Developer", style=discord.ButtonStyle.primary, custom_id="role_dev")
    async def dev(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_choice(interaction, "dev")

    @ui.button(label="Marketing", style=discord.ButtonStyle.primary, custom_id="role_marketing")
    async def marketing(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_choice(interaction, "marketing")

    async def handle_choice(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ You can't interact with this menu.", ephemeral=True
            )
            return

        # Enregistrer la sélection
        user_onboarding[self.user_id] = choice
        await interaction.response.edit_message(
            content=f"✅ You chose **{choice.replace('_', ' ').title()}**! Onboarding continues...",
            view=None
        )
        # Ici tu peux lancer l'étape suivante de l'onboarding


class TicketOnboarding(commands.Cog):
    """Cog qui gère l'onboarding dans les tickets dès leur ouverture."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots et messages hors serveur
        if message.author.bot or not message.guild:
            return

        # Détecte les channels de tickets (nom commence par 'ticket-')
        if not message.channel.name.startswith("ticket-"):
            return

        user_id = message.author.id

        # On ne propose le choix qu'une seule fois
        if user_id in user_onboarding:
            return

        # Envoyer le message d'intro avec boutons pour choix de rôle
        embed = discord.Embed(
            title="Welcome to Pi RPG Onboarding!",
            description=(
                "Please select the role you are applying for by clicking one of the buttons below:\n"
                "- Pixel Artist\n"
                "- Developer\n"
                "- Marketing"
            ),
            color=0x00FF00
        )
        view = OnboardingView(user_id)
        await message.channel.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketOnboarding(bot))
