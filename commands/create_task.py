import discord
from discord.ui import Select, View
from discord import app_commands
import config

@discord.app_commands.command(name="createtask", description="Create a new task (Admins only)")
@app_commands.describe(title="Title of the task", description="Task details")
async def create_task(interaction: discord.Interaction, title: str, description: str):
    await interaction.response.defer(ephemeral=True)

    # Création des options de sélection pour la catégorie
    category_options = [discord.SelectOption(label=key, value=key) for key in config.TASKS_CHANNEL_ID.keys()]
    category_select = Select(placeholder="Choose a category...", options=category_options, custom_id="category_select")

    # Création de la vue et ajout du sélecteur de catégorie
    view = View()
    view.add_item(category_select)

    await interaction.followup.send(f"📝 Please choose a category for the task **{title}**:", view=view, ephemeral=True)

    def check(inter: discord.Interaction):
        return inter.user == interaction.user

    # Attente de la sélection de la catégorie par l'utilisateur
    select = await interaction.client.wait_for("interaction", check=check)
    category = select.data['values'][0]

    # Récupération du channel associé à la catégorie
    channel_id = config.TASKS_CHANNEL_ID.get(category)
    if not channel_id:
        await interaction.followup.send("❌ Invalid category selected.", ephemeral=True)
        return

    # Récupération du canal
    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        await interaction.followup.send("❌ The selected channel is not available.", ephemeral=True)
        return

    # Création du message embed pour la tâche
    embed = discord.Embed(title=f"{title}", description=description, color=0xF4E3C7)
    embed.set_thumbnail(url="https://example.com/image.png")
    embed.add_field(name="👤 Assigned to", value="None", inline=True)
    embed.add_field(name="🔄️ Status", value="To Do", inline=True)
    # Envoi du message dans le canal
    message = await channel.send(embed=embed)
    await interaction.followup.send(f"✅ Task **{title}** created in {channel.mention} with card **{card_name}**.", ephemeral=True)

# Fonction setup obligatoire pour chaque extension
async def setup(bot):
    bot.tree.add_command(create_task)
