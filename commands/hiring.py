import discord
from discord.ext import commands
import os

MESSAGE_TRACKING_FILE = "recruitment_message_id.txt"

class Recruitment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1400511222394126367  # Canal du message de lancement
        self.role_channel_map = {
            "pixelart": 1355852568806293637,
            "dev": 1363812990566006865,
            "marketing": 333333333333333333
        }
        self.user_roles = {}  # UserID -> role
        self.role_doc_links = {
            "pixelart": "https://docs.google.com/document/d/1s-idcJdVd1y6kDG6kkLNPBaGGvPtpUEf/edit?usp=sharing&ouid=113302409645000036167&rtpof=true&sd=true",
            "dev": "https://example.com/recrutement_dev.pdf",
            "marketing": "https://example.com/recrutement_marketing.pdf"
        }

    async def setup(self):
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print(f"[Recruitment] Channel ID {self.channel_id} introuvable.")
            return

        # Lire le message_id s'il existe
        message_id = None
        if os.path.exists(MESSAGE_TRACKING_FILE):
            with open(MESSAGE_TRACKING_FILE, "r") as f:
                try:
                    message_id = int(f.read().strip())
                except ValueError:
                    pass

        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(view=ApplyButtonView(self))  # recharge les boutons
                print("[Recruitment] Message initial rechargé avec succès.")
                return
            except discord.NotFound:
                print("[Recruitment] Ancien message non trouvé, envoi d'un nouveau.")

        # Nouveau message si non trouvé
        embed = discord.Embed(
            title="🚀 Recrutement ouvert !",
            description="Clique sur **Postuler** pour démarrer ta candidature.",
            color=discord.Color.blurple()
        )
        message = await channel.send(embed=embed, view=ApplyButtonView(self))

        # Sauvegarder le nouveau message ID
        with open(MESSAGE_TRACKING_FILE, "w") as f:
            f.write(str(message.id))
        print("[Recruitment] Nouveau message de recrutement envoyé.")


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

        ticket_channel = await guild.create_text_channel(f"ticket-{user.name}", overwrites=overwrites, category=category)
        await ticket_channel.send(f"{user.mention}, quel rôle vous intéresse ?", view=RoleChoiceView(self.cog, user))


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

        link = self.cog.role_doc_links.get(role)
        await interaction.response.send_message(
            f"📄 Voici le document pour le rôle **{role}** :\n{link}",
            ephemeral=True
        )

        await interaction.followup.send(
            "Souhaites-tu poursuivre et choisir une tâche ?",
            view=ContinueView(self.cog, self.user),
            ephemeral=True
        )


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
            await interaction.response.send_message("❌ Aucun salon de tâches trouvé.", ephemeral=True)
            return

        messages = [msg async for msg in channel.history(limit=50) if msg.embeds]

        if not messages:
            await interaction.response.send_message("🕐 Aucune tâche disponible pour l’instant.", ephemeral=True)
            return

        options = []
        for msg in messages[:25]:  # Limite Discord
            embed = msg.embeds[0]
            label = embed.title[:80] if embed.title else "Tâche sans titre"
            options.append(discord.SelectOption(label=label, value=str(msg.id)))

        view = TaskChoiceView(options)
        await interaction.response.send_message("Voici les tâches disponibles :", view=view, ephemeral=True)


class TaskSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choisis une tâche :", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        task_id = self.values[0]
        channel = interaction.channel
        try:
            task_msg = await channel.fetch_message(int(task_id))
            task_link = task_msg.jump_url
            await interaction.response.send_message(
                f"✅ Utilise `/assign_task {task_id}` pour t’assigner cette tâche.\n🔗 {task_link}",
                ephemeral=True
            )
        except:
            await interaction.response.send_message("❌ Impossible de récupérer la tâche.", ephemeral=True)


    @discord.ui.button(label="Oui, je veux voir les tâches", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = self.cog.user_roles.get(self.user.id)
        task_channel_id = self.cog.role_channel_map.get(role)
        channel = interaction.guild.get_channel(task_channel_id)

        if not channel:
            await interaction.response.send_message("❌ Aucun salon de tâches trouvé.", ephemeral=True)
            return

        messages = [msg async for msg in channel.history(limit=20) if not msg.author.bot]
        if not messages:
            await interaction.response.send_message("🕐 Aucune tâche disponible pour l’instant.", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=msg.content[:80], value=str(msg.id))
            for msg in messages[:25]  # Discord limite à 25 options
        ]

        view = TaskChoiceView(options)
        await interaction.response.send_message("Voici les tâches disponibles :", view=view, ephemeral=True)


class TaskChoiceView(discord.ui.View):
    def __init__(self, options):
        super().__init__(timeout=None)
        self.add_item(TaskSelect(options))


# Pour charger l'extension
async def setup(bot):
    cog = Recruitment(bot)
    await bot.add_cog(cog)
    await cog.setup()
