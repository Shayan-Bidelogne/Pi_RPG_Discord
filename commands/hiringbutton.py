import discord
from discord import app_commands, ui
from discord.ext import commands

STAFF_IDS = [111111111111111111, 222222222222222222]  # Remplace par tes IDs staff
EXISTING_MESSAGE_ID = 1447639852861624591
EXISTING_CHANNEL_ID = 1447627589295538296

class HiringView(ui.View):
    def __init__(self, bot: commands.Bot, timeout: int | None = None):
        super().__init__(timeout=timeout)  # timeout=None pour view persistante
        self.bot = bot

    @ui.button(label="Apply", custom_id="hiring_open_ticket", style=discord.ButtonStyle.primary)
    async def apply_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        applicant = interaction.user

        # Nom du salon ticket sécurisé
        safe_name = f"ticket-{applicant.name}".lower().replace(" ", "-")[:90]

        # Permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            applicant: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        for staff_id in STAFF_IDS:
            overwrites[discord.Object(id=staff_id)] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # Parent category si possible
        parent = interaction.channel.category if interaction.channel and isinstance(interaction.channel, discord.TextChannel) else None

        # Création du ticket
        ticket_channel = await guild.create_text_channel(
            name=safe_name,
            overwrites=overwrites,
            category=parent,
            reason=f"Ticket opened by {applicant} via hiring button"
        )

        await ticket_channel.send(f"Welcome <@{applicant.id}> — a team member will assist you shortly.")
        await interaction.followup.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

class HiringEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ⚡ Enregistrement de la View persistante dès le démarrage
        self.bot.add_view(HiringView(bot, timeout=None), message_id=EXISTING_MESSAGE_ID)

    @app_commands.command(name="hiring", description="Post the recruitment embed with Apply button (admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def hiring(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed_recruit = discord.Embed(
            title="🚀 Pi RPG is Hiring! Join the Team.",
            description=(
                "_We’re expanding the Pi RPG project and opening key roles for passionate collaborators:_\n\n"
                "## 🎮 **Godot Developer**\n"
                "Help bring the world of Pi RPG to life with smooth mechanics, exploration systems, and combat logic.\n\n"
                "## 🎨 **Pixel Artist / Pixel Animator**\n"
                "Shape the visual identity of Pi RPG — characters, environments, abilities, and animations.\n\n"
                "## 📣 **Public Relations**\n"
                "You’ll be the voice of Pi RPG: community engagement, social media planning, announcements.\n\n"
                "## **You can find more info on our website** 👉 https://pirpg.netlify.app/"
            ),
            color=0xFFA500
        )
        embed_recruit.set_image(url="https://pbs.twimg.com/media/GwQZGjtWIAAy4yU?format=jpg&name=small")
        embed_recruit.set_footer(
            text="Join the adventure!",
            icon_url="https://media.discordapp.net/attachments/1354459544818028714/1447063656377487544/LogoPi2.png"
        )
        embed_recruit.timestamp = discord.utils.utcnow()

        # Vue persistante
        view = HiringView(self.bot, timeout=None)
        msg = await interaction.channel.send(embed=embed_recruit, view=view)

        # ⚡ Enregistrement de la View persistante pour le nouveau message
        self.bot.add_view(view, message_id=msg.id)

        await interaction.followup.send("Recruitment embed posted. Button is now persistent.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HiringEmbed(bot))
