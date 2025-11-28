import discord
from discord import app_commands
import config

@discord.app_commands.command(name="task", description="Assign yourself a task by title")
@app_commands.describe(title="Title of the task")
async def task(interaction: discord.Interaction, title: str):
    # Parcourir tous les canaux définis dans config.TASKS_CHANNEL_ID
    for channel_id in config.TASKS_CHANNEL_ID.values():
        channel = interaction.client.get_channel(channel_id)
        
        if not channel:  # Vérification si le canal est valide
            await interaction.response.send_message(f"❌ Channel with ID {channel_id} is not available.", ephemeral=True)
            return
        
        async for message in channel.history(limit=100):
            if message.embeds:
                embed = message.embeds[0]
                # Comparer le titre de la tâche avec le titre de l'embed
                if embed.title.strip() == f"{title}":
                    embed.set_field_at(0, name="👤 Assigned to", value=interaction.user.mention, inline=True)
                    await message.edit(embed=embed)
                    await interaction.response.send_message(f"✏️ {interaction.user.mention} has taken task **{title}**", ephemeral=True)
                    return

    # Si aucune tâche n'a été trouvée
    await interaction.response.send_message("❌ Task not found.", ephemeral=True)

# Fonction setup obligatoire pour chaque extension
async def setup(bot):
    bot.tree.add_command(task)
