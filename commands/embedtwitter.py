import discord
from discord import app_commands, ui
from discord.ext import commands

class PubEmbed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ad", description="Publish a preconfigured advertisement embed")
    async def pubembed(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # ========= EMBED 1 ========= #
        embed1 = discord.Embed(
            title="Pi RPG — Adventure, Craft & Earn!",
            description="🌋 Explore dangerous maps, face epic bosses & master crafting!\n💰 Play-to-Earn via **Pi Network** — earn and play!\n👉 https://discord.gg/mexYcAFEc9",
            color=0xFFA500
        )
        embed1.set_image(url="https://images-ext-1.discordapp.net/external/U_Hm_A20CHCO40dYHcIIXUcl_55h9EXoWrrtIW2TuvY/https/pbs.twimg.com/media/G7hculhWsAAoG2q.png?format=webp&quality=lossless&width=881&height=880")
        embed1.set_footer(text="Join now! 🔥", icon_url="https://media.discordapp.net/attachments/1354459544818028714/1447063656377487544/LogoPi2.png")
        embed1.timestamp = discord.utils.utcnow()

        # ========= EMBED 3 (RECRUITMENT) ========= #
        embed_recruit = discord.Embed(
            title="🚀 Pi RPG is Recruiting! Join the Team.",
            description=(
                "_We’re expanding the Pi RPG project and opening key roles for passionate collaborators:_\n\n"
                "## 🎮 **Godot Developer**\n"
                "Help bring the world of Pi RPG to life with smooth mechanics, exploration systems, and combat logic.\n\n"
                "## 🎨 **Pixel Artist / Pixel Animator**\n"
                "Shape the visual identity of Pi RPG — characters, environments, abilities, and animations.\n\n"
                "## 📣 **Public Relations**\n"
                "You’ll be the voice of Pi RPG: community engagement, social media planning, announcements.\n\n"
                "## **You can apply/find more info on our website** 👉 [Pi RPG Website](https://pirpg.netlify.app/)"
            ),
            color=0xFFA500
        )
        embed_recruit.set_image(
            url="https://pbs.twimg.com/media/GwQZGjtWIAAy4yU?format=jpg&name=small"
        )
        embed_recruit.set_footer(
            text="Join the adventure!",
            icon_url="https://media.discordapp.net/attachments/1354459544818028714/1447063656377487544/LogoPi2.png"
        )
        embed_recruit.timestamp = discord.utils.utcnow()

        # ========= EMBED LIST ========= #
        embeds_list = {
            "pub1": ("🔥 Ad — Discord Server", embed1),
            "pub3": ("🚀 Ad — Hiring", embed_recruit),
        }

        # ========= SELECT MENU ========= #
        class EmbedSelect(ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=name, value=key)
                    for key, (name, _) in embeds_list.items()
                ]
                super().__init__(placeholder="Select an embed to publish…", options=options)

            async def callback(self, select_interaction: discord.Interaction):
                key = self.values[0]
                selected_embed = embeds_list[key][1]

                await interaction.channel.send(embed=selected_embed)
                await select_interaction.response.edit_message(
                    content=f"✅ Embed **{embeds_list[key][0]}** posted in {interaction.channel.mention}!",
                    view=None
                )
                self.view.stop()

        class EmbedView(ui.View):
            def __init__(self):
                super().__init__(timeout=120)
                self.add_item(EmbedSelect())

        await interaction.followup.send(
            "📢 Choose the embed you want to publish:",
            view=EmbedView(),
            ephemeral=True
        )

# ========= Setup ========= #
async def setup(bot):
    await bot.add_cog(PubEmbed(bot))
