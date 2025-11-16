import discord
from discord import app_commands
import config

@discord.app_commands.command(name="assigntask", description="Assign a task to a user (Admin only)")
@app_commands.describe(title="Title of the task", assignee="User to assign the task to")
async def assign_task(interaction: discord.Interaction, title: str, assignee: discord.Member):
    # Vérifier si l'utilisateur a le rôle autorisé
    if not any(role.id == config.AUTHORIZED_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("⛔ You don't have permission to assign tasks.", ephemeral=True)
        return

    for channel_id in config.TASKS_CHANNEL_ID.values():
        channel = interaction.client.get_channel(channel_id)
        if channel is None:
            continue
        async for message in channel.history(limit=100):
            if message.embeds:
                embed = message.embeds[0]
                if embed.title.strip() == title:
                    embed.set_field_at(0, name="👤 Assigned to", value=assignee.mention, inline=True)
                    await message.edit(embed=embed)
                    await interaction.response.send_message(f"✅ Task **{title}** assigned to {assignee.mention}", ephemeral=True)
                    return
    await interaction.response.send_message("❌ Task not found.", ephemeral=True)

# Fonction setup obligatoire pour chaque extension
async def setup(bot):
    bot.tree.add_command(assign_task)
