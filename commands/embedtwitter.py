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
            title="🎮 Pi RPG — Adventure, Craft & Earn!",
            description="🌋 Explore volcano fields, face epic bosses & master crafting!\n💰 Play-to-Earn via **Pi Network** — earn rewards while playing!",
            color=0xFFA500  # Orange
        )
        embed.set_image(url="https://your-image-link-here.com/image.png")  # Remplace par ton image
        embed.set_footer(text="Join now! 🔥", icon_url="https://cdn-icons-png.flaticon.com/512/25/25231.png")
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
