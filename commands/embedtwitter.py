import discord
from discord import app_commands, ui
from discord.ext import commands

class PubEmbed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pubembed", description="Partager un embed style pub du serveur/jeu")
    async def pubembed(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Crée l'embed
        embed = discord.Embed(
            title="Pi RPG — Adventure, Craft & Earn!",
            description="🌋 Explore dangerous maps, face epic bosses & master crafting!\n💰 Play-to-Earn via **Pi Network** — earn rewards while playing!\n### 👉 https://discord.gg/mexYcAFEc9",
            color=0xFFA500  # Orange
        )
        embed.set_image(url="https://images-ext-1.discordapp.net/external/U_Hm_A20CHCO40dYHcIIXUcl_55h9EXoWrrtIW2TuvY/https/pbs.twimg.com/media/G7hculhWsAAoG2q.png?format=webp&quality=lossless&width=881&height=880")  # Remplace par ton image
        embed.set_footer(text="Join now! 🔥", icon_url="https://media.discordapp.net/attachments/1354459544818028714/1447063656377487544/LogoPi2.png?ex=6936428c&is=6934f10c&hm=910c457ef7ade36f1eebc39c9aa93e4e5375239eb904c9f46db0e12fe7b6f1eb&=&format=webp&quality=lossless&width=840&height=840")
        embed.timestamp = discord.utils.utcnow()

        # Envoie un Select Menu pour confirmer la pub
        class ConfirmSelect(ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="Oui, publier !", value="yes"),
                    discord.SelectOption(label="Annuler", value="no")
                ]
                super().__init__(placeholder="Confirme la publication...", options=options, min_values=1, max_values=1)

            async def callback(self, select_interaction: discord.Interaction):
                if self.values[0] == "yes":
                    await interaction.channel.send(embed=embed)
                    await select_interaction.response.edit_message(content="✅ Embed publié !", view=None)
                else:
                    await select_interaction.response.edit_message(content="❌ Publication annulée.", view=None)
                self.view.stop()

        class ConfirmView(ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(ConfirmSelect())

        await interaction.followup.send("📢 Veux-tu publier cet embed ?", view=ConfirmView(), ephemeral=True)

# ================== Setup ==================
async def setup(bot):
    await bot.add_cog(PubEmbed(bot))
