# cogs/onboarding_auto.py
import discord
from discord import ui
from discord.ext import commands

STAFF_IDS = [111111111111111111, 222222222222222222]  # IDs staff autorisés

class OnboardingView(ui.View):
    def __init__(self, bot: commands.Bot, user: discord.Member, step: int = 1, timeout: int | None = None):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user = user
        self.step = step  # étape actuelle

    @ui.button(label="✅", style=discord.ButtonStyle.success, custom_id="onboarding_yes")
    async def yes(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your onboarding.", ephemeral=True)
            return
        await self.next_step(interaction, True)

    @ui.button(label="❌", style=discord.ButtonStyle.danger, custom_id="onboarding_no")
    async def no(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("This is not your onboarding.", ephemeral=True)
            return
        await self.next_step(interaction, False)

    async def next_step(self, interaction: discord.Interaction, answer: bool):
        """Gérer le passage à l'étape suivante"""
        if self.step == 1:
            if answer:
                self.step += 1
                await interaction.response.edit_message(
                    content="✅ Great! Next step: Have you joined our Discord community?",
                    view=self
                )
            else:
                await interaction.response.edit_message(
                    content="❌ Please read the info on our website before continuing.",
                    view=self
                )
        elif self.step == 2:
            if answer:
                self.step += 1
                await interaction.response.edit_message(
                    content="✅ Awesome! Final step: Do you accept the rules?",
                    view=self
                )
            else:
                await interaction.response.edit_message(
                    content="❌ Please join the Discord to continue.",
                    view=self
                )
        elif self.step == 3:
            if answer:
                await interaction.response.edit_message(
                    content="🎉 Onboarding completed! Welcome to the team.",
                    view=None
                )
            else:
                await interaction.response.edit_message(
                    content="❌ You must accept the rules to continue.",
                    view=self
                )

class OnboardingAuto(commands.Cog):
    """Démarre automatiquement l'onboarding dans les tickets."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        # Vérifier que c'est un text channel
        if not isinstance(channel, discord.TextChannel):
            return

        # Vérifier que c'est un ticket ouvert par HiringView
        if channel.name.startswith("ticket-"):
            # Chercher le membre correspondant à l'auteur (nom dans le channel)
            username = channel.name[len("ticket-"):].replace("-", " ")
            member = discord.utils.find(lambda m: m.name.lower() == username.lower(), channel.guild.members)
            if not member:
                return  # pas trouvé

            # Poster automatiquement l'onboarding
            view = OnboardingView(self.bot, user=member)
            await channel.send(
                f"Welcome {member.mention}! Let's start your onboarding.\n\nStep 1: Did you read all info on the website?",
                view=view
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(OnboardingAuto(bot))
