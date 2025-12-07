import os
import discord
from discord import app_commands, ui
from discord.ext import commands

# ================== Config ==================
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "1439549538556973106"))

# ================== Cog ==================
class TwitterEmbed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="twitterembed", description="Partager un tweet de la librairie dans ce channel")
    async def twitterembed(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not channel:
            await interaction.followup.send("❌ Channel librairie introuvable.", ephemeral=True)
            return

        messages = [msg async for msg in channel.history(limit=100) if msg.embeds]
        if not messages:
            await interaction.followup.send("❌ Aucun tweet trouvé dans la librairie.", ephemeral=True)
            return

        # Crée les options du Select Menu
        options = []
        for i, msg in enumerate(messages):
            desc = msg.embeds[0].description or "[No text]"
            label = desc.replace("\n"," ")[:90]  # max 100 caractères
            options.append(discord.SelectOption(label=f"#{i+1} - {label}", value=str(i)))

        class TweetSelect(ui.Select):
            def __init__(self):
                super().__init__(placeholder="Choisis un tweet...", options=options, min_values=1, max_values=1)

            async def callback(self, select_interaction: discord.Interaction):
                idx = int(self.values[0])
                tweet_msg = messages[idx]
                # Copier l'embed
                embeds = tweet_msg.embeds
                target_channel = interaction.channel
                if not target_channel:
                    await select_interaction.response.send_message("❌ Impossible de trouver ce channel.", ephemeral=True)
                    return
                for emb in embeds:
                    await target_channel.send(embed=emb)
                await select_interaction.response.send_message(f"✅ Tweet partagé dans {target_channel.mention}", ephemeral=True)
                self.view.stop()

        class TweetView(ui.View):
            def __init__(self):
                super().__init__(timeout=120)
                self.add_item(TweetSelect())

        await interaction.followup.send("📚 Sélectionne un tweet à partager :", view=TweetView(), ephemeral=True)

# ================== Setup ==================
async def setup(bot):
    await bot.add_cog(TwitterEmbed(bot))
