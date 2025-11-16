import discord
from discord.ext import commands

TICKET_CATEGORY_NAME = "Tickets"

# Liste des rôles qui déclenchent la réaction
ROLE_NAMES_FOR_REACTION = [
    "Pixel Artist",
    "Developer",
    "Marketing"
]

# Emoji personnalisé
EMOJI_REACTION = "<:Pi2:123456789012345678>"   # ← Mets l'ID de ton emoji ici


class RoleReactionListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore les bots ou messages vides
        if message.author.bot:
            return

        # Vérifie si le message est dans la catégorie "Tickets"
        if message.channel.category and message.channel.category.name == TICKET_CATEGORY_NAME:

            # Récupère les noms de roles du membre
            user_roles = [role.name for role in message.author.roles]

            # Check si AU MOINS un des rôles correspond
            if any(role in user_roles for role in ROLE_NAMES_FOR_REACTION):
                try:
                    await message.add_reaction(EMOJI_REACTION)
                except Exception as e:
                    print(f"[RoleReactionListener] Impossible d’ajouter la réaction : {e}")


async def setup(bot):
    await bot.add_cog(RoleReactionListener(bot))
