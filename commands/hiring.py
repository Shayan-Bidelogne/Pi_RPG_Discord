import discord
from discord.ext import commands
import os

MESSAGE_TRACKING_FILE = "recruitment_message_id.txt"
SPECIAL_ROLE_ID = 1400684870686081045  # Remplace par l'ID du rôle à donner/retirer

class Recruitment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1400511222394126367  # Canal du message de lancement
        self.role_channel_map = {
            "pixelart": 1355852568806293637,
            "dev": 1363812990566006865,
            "marketing": 31401139679423631430
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
            print(f"[Recruitment] Channel ID {self.channel_id} not found.")
            return

        message_id = None
        if os.path.exists(MESSAGE_TRACKING_FILE):
            with open(MESSAGE_TRACKING_FILE, "r") as f:
                content = f.read().strip()
                print(f"[Recruitment] ID read from file: {content}")
                try:
                    message_id = int(content)
                except ValueError:
                    print("[Recruitment] Invalid message ID in file.")
                    message_id = None

        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(view=ApplyButtonView(self))
                print("[Recruitment] Recruitment message successfully reloaded.")
                return
            except discord.NotFound:
                print("[Recruitment] Previous message not found, sending a new one.")
            except discord.Forbidden:
                print("[Recruitment] Forbidden: cannot fetch or edit the message.")
            except Exception as e:
                print(f"[Recruitment] Unexpected error: {e}")

        # Only here do we send a new message and overwrite the file
        embed = discord.Embed(
            title="🚀 Recruitment open!",
            description="Click **Apply** to start your application.",
            color=discord.Color(0xF3E2C6)
        )
        message = await channel.send(embed=embed, view=ApplyButtonView(self))

        with open(MESSAGE_TRACKING_FILE, "w") as f:
            f.write(str(message.id))
        print("[Recruitment] New recruitment message sent.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        role = member.guild.get_role(SPECIAL_ROLE_ID)
        if role:
            await member.add_roles(role, reason="Automatic role on join")


class ApplyButtonView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="📝 Apply", style=discord.ButtonStyle.secondary)
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        # Remove the special role
        role = guild.get_role(SPECIAL_ROLE_ID)
        if role and role in user.roles:
            await user.remove_roles(role, reason="Role removed after application")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")

        ticket_channel = await guild.create_text_channel(f"ticket-{user.name}", overwrites=overwrites, category=category)

        await ticket_channel.send(
            f"👋 Welcome {user.mention}!\n\n"
            "This private channel will guide you through our recruitment process.\n"
            "Here's how it works:\n"
            "1. You'll choose the role you're applying for.\n"
            "2. You'll receive a short document explaining what we expect.\n"
            "3. If you’re motivated, you can choose a task and try it out!\n\n"
            "Please start by selecting the role you're interested in below 👇"
        )

        await ticket_channel.send(view=RoleChoiceView(self.cog, user))

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
            f"📄 Here is the document for the role **{role}**:\n{link}",
            ephemeral=True
        )

        await interaction.followup.send(
            "Do you want to continue and choose a task?",
            view=ContinueView(self.cog, self.user),
            ephemeral=True
        )


class ContinueView(discord.ui.View):
    def __init__(self, cog, user):
        super().__init__(timeout=None)
        self.cog = cog
        self.user = user

    @discord.ui.button(label="Yes I want to do my first task !", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = self.cog.user_roles.get(self.user.id)
        task_channel_id = self.cog.role_channel_map.get(role)
        channel = interaction.guild.get_channel(task_channel_id)

        if not channel:
            await interaction.response.send_message("❌ No task channel found.", ephemeral=True)
            return

        messages = [msg async for msg in channel.history(limit=50) if msg.embeds]

        if not messages:
            await interaction.response.send_message("🕐 No tasks available at the moment.", ephemeral=True)
            return

        options = []
        for msg in messages[:25]:
            embed = msg.embeds[0]
            label = embed.title[:80] if embed.title else "Tâche sans titre"
            options.append(discord.SelectOption(label=label, value=str(msg.id)))

        view = TaskChoiceView(options, self.user, self.cog)
        await interaction.response.send_message("Here are the available tasks:", view=view, ephemeral=True)


class TaskSelect(discord.ui.Select):
    def __init__(self, options, user, cog):
        self.user = user
        self.cog = cog
        super().__init__(placeholder="Choisis une tâche :", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        task_id = self.values[0]
        role = self.cog.user_roles.get(self.user.id)
        task_channel_id = self.cog.role_channel_map.get(role)
        channel = interaction.guild.get_channel(task_channel_id)
        if not channel:
            await interaction.response.send_message("❌ Salon de tâches introuvable.", ephemeral=True)
            return
        try:
            task_msg = await channel.fetch_message(int(task_id))
            embed = task_msg.embeds[0]
            # Affiche l'embed et propose la validation
            view = ConfirmAssignView(task_msg, embed, self.user, self.cog)
            await interaction.response.send_message(
                "Here is the detail of the selected task. Do you want to confirm the assignment?",
                embed=embed,
                view=view,
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Impossible de récupérer la tâche. {e}", ephemeral=True)


class ConfirmAssignView(discord.ui.View):
    def __init__(self, task_msg, embed, user, cog):
        super().__init__(timeout=120)
        self.task_msg = task_msg
        self.embed = embed
        self.user = user
        self.cog = cog

    @discord.ui.button(label="Confirm assignment", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        assigned_field = None
        for i, field in enumerate(self.embed.fields):
            if field.name == "👤 Assigned to":
                assigned_field = field
                field_index = i
                break
        if assigned_field and assigned_field.value != "None":
            await interaction.response.send_message(
                f"❌ This task is already assigned to {assigned_field.value}.",
                ephemeral=True
            )
            self.stop()
            return
        # Assign the user
        self.embed.set_field_at(field_index, name="👤 Assigned to", value=self.user.mention, inline=True)
        await self.task_msg.edit(embed=self.embed)
        await interaction.response.send_message(
            f"✅ Task **{self.embed.title}** successfully assigned to {self.user.mention}.",
            ephemeral=True
        )
        # Close current ticket channel
        current_channel = interaction.channel
        try:
            await current_channel.delete(reason="Ticket closed after task assignment")
        except Exception:
            pass
        # Create new ticket channel and send the embed
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        }
        new_channel = await guild.create_text_channel(f"ticket-{self.user.name}", overwrites=overwrites, category=category)
        await new_channel.send(f"{self.user.mention}, here is your assigned task:", embed=self.embed)
        self.stop()


class TaskChoiceView(discord.ui.View):
    def __init__(self, options, user, cog):
        super().__init__(timeout=None)
        self.add_item(TaskSelect(options, user, cog))


async def setup(bot):
    cog = Recruitment(bot)
    await bot.add_cog(cog)
    await cog.setup()
