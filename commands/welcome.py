import discord
from discord.ext import commands

WELCOME_ROLE_NAME = "5"  # Le nom exact du rôle que tu veux attribuer
WELCOME_MESSAGE = """
Bonjour {user} ! 🎉
Bienvenue sur le serveur ! Nous sommes ravis de t'avoir parmi nous.
"""

class WelcomeDM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Envoie un message de bienvenue en DM
        try:
            await member.send(WELCOME_MESSAGE.format(user=member.mention))
        except Exception as e:
            print(f"[WelcomeDM] Impossible d'envoyer le DM à {member}: {e}")

        # Attribue le rôle @5
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
