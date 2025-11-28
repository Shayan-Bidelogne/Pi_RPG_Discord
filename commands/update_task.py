import discord
from discord.ui import Select, View
from discord import app_commands
import config

@discord.app_commands.command(name="updatetask", description="Update the status of a task by title")
@app_commands.describe(title="Title of the task")
async def update_task(interaction: discord.Interaction, title: str):
    options = [discord.SelectOption(label=state, value=state) for state in ["To Do", "In Progress", "Done"]]
    select_menu = Select(placeholder="Choose a status...", options=options, custom_id="status_select_menu")
    view = View()
    view.add_item(select_menu)
    
    # Envoi du message pour sélectionner un statut
    await interaction.response.send_message(f"🔄 Please choose a status for task **{title}**:", view=view, ephemeral=True)

    # Fonction de vérification pour s'assurer que c'est le même utilisateur qui interagit
    def check(inter: discord.Interaction):
        return inter.user == interaction.user

    try:
        select = await interaction.client.wait_for("interaction", check=check)
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ Timeout: You didn't choose a status in time.", ephemeral=True)
        return

    status = select.data['values'][0]
    
    # Chercher la tâche dans tous les canaux définis dans config.TASKS_CHANNEL_ID
    for channel_id in config.TASKS_CHANNEL_ID.values():
        channel = interaction.client.get_channel(channel_id)
        if not channel:
            continue  # Si le canal n'existe pas, passer à l'itération suivante
        
        async for message in channel.history(limit=100):
            if message.embeds:
                embed = message.embeds[0]
                if embed.title.strip() == f"{title}":
                    embed.set_field_at(1, name="🔄️ Status", value=status, inline=True)
                    await message.edit(embed=embed)
                    await interaction.followup.send(f"🔄 Task **{title}** status updated to **{status}**", ephemeral=True)
                    return
    
    # Si la tâche n'a pas été trouvée
    await interaction.followup.send("❌ Task not found.", ephemeral=True)

# Fonction setup obligatoire pour chaque extension
async def setup(bot):
    bot.tree.add_command(update_task)
