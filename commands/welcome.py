import discord
from discord.ext import commands

WELCOME_ROLE_NAME = "5"  # Nom exact du rôle à attribuer

class WelcomeDM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        # === ✅ EMBED DE BIENVENUE ===
        embed = discord.Embed(
            title="🎉 Welcome to Pi RPG!",
            description=(
                "Its the beginning of your journey in the fabulous Pi RPG's world!\n\n"
                "**Create your account to get started** 👇"
            ),
            color=0xF39C12  # 🟧 ORANGE HEX ✅
        )

        embed.set_thumbnail(url="https://i.imgur.com/0y0y0y0.png")  # change si tu veux
        embed.set_footer(text="Pi RPG • Let the adventure begin")

        # === ✅ BOUTON CLIQUABLE ===
        class AccountButton(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                self.add_item(discord.ui.Button(
                    label="Create your account",
                    url="https://pirpg.netlify.app/pi_rpg_bourse/login",
                    style=discord.ButtonStyle.link  # Obligatoire pour lien 🔗
                ))

        try:
            await member.send(embed=embed, view=AccountButton())
        except Exception as e:
            print(f"[WelcomeDM] Impossible d'envoyer le DM à {member}: {e}")

        # === ✅ ATTRIBUTION DU RÔLE @5 ===
        role = discord.utils.get(member.guild.roles, name=WELCOME_ROLE_NAME)
        if role:
            try:
                await member.add_roles(role)
                print(f"[WelcomeDM] Rôle '{role.name}' attribué à {member}.")
            except Exception as e:
                print(f"[WelcomeDM] Impossible d'attribuer le rôle à {member}: {e}")
        else:
            print(f"[WelcomeDM] Rôle '{WELCOME_ROLE_NAME}' introuvable sur le serveur.")

async def setup(bot):
    await bot.add_cog(WelcomeDM(bot))
