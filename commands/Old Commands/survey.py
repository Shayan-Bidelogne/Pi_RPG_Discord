import discord
from discord.ui import Select, View
from discord import app_commands
import config

@discord.app_commands.command(name="survey", description="Créer un sondage avec des options de vote")
@app_commands.describe(question="La question du sondage", options="Les options séparées par un point-virgule (;) ex: Option1;Option2;Option3")
async def survey(interaction: discord.Interaction, question: str, options: str):
    # Diviser les options
    option_list = [opt.strip() for opt in options.split(";") if opt.strip()]
    
    if len(option_list) < 2 or len(option_list) > 10:
        await interaction.response.send_message("❌ Tu dois fournir entre 2 et 10 options, séparées par des `;`", ephemeral=True)
        return

    # Créer l'embed du sondage
    embed = discord.Embed(title="📊 Survey", description=question, color=0xF4E3C7)
    embed.set_thumbnail(url="https://example.com/image.png")
    
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, option in enumerate(option_list):
        embed.add_field(name=f"{emojis[i]}", value=option, inline=False)

    # Envoyer l'embed et ajouter les réactions
    await interaction.response.send_message("✅ Sondage créé :", ephemeral=True)
    message = await interaction.channel.send(embed=embed)

    # Vérification si le message a bien été envoyé avant d'ajouter des réactions
    if message:
        for i in range(len(option_list)):
            await message.add_reaction(emojis[i])

# Fonction setup obligatoire pour chaque extension
async def setup(bot):
    bot.tree.add_command(survey)
