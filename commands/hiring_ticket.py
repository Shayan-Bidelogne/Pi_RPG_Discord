import discord
from discord.ext import commands

# IDs des rôles utilisés comme trigger (pas pour attribution)
ROLE_IDS = {
    "pixel_artist": 1354456280303014108,
    "dev": 1354456244827459695,
    "marketing": 1369649449495826466,
}

# Pour suivre l'état de l'onboarding par utilisateur
user_onboarding = {}


class TicketOnboarding(commands.Cog):
    """Cog qui gère l'onboarding déclenché par le tag d'un rôle dans un ticket."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots et messages hors serveur
        if message.author.bot or not message.guild:
            return

        # Détecte les channels de tickets (nom commence par 'ticket-')
        if not message.channel.name.startswith("ticket-"):
            return

        user_id = message.author.id

        # Ne pas relancer l'onboarding si déjà déclenché
        if user_id in user_onboarding:
            return

        # Vérifier si le message mentionne un rôle qui est dans nos ROLE_IDS
        chosen_role = None
        for role in message.role_mentions:
            for key, role_id in ROLE_IDS.items():
                if role.id == role_id:
                    chosen_role = key
                    break
            if chosen_role:
                break

        if not chosen_role:
            return  # Aucun rôle taggué qui nous intéresse

        # Enregistrer la sélection
        user_onboarding[user_id] = chosen_role

        # Envoyer l'onboarding personnalisé selon le rôle
        if chosen_role == "pixel_artist":
            description = (
                f"🎨 {message.author.mention}, you chose Pixel Artist! "
                "Can you share your portfolio or previous work?"
            )
        elif chosen_role == "dev":
            description = (
                f"💻 {message.author.mention}, you chose Developer! "
                "Can you share your coding experience or projects?"
            )
        elif chosen_role == "marketing":
            description = (
                f"📣 {message.author.mention}, you chose Marketing! "
                "Let's talk about marketing!"
            )
        else:
            description = f"{message.author.mention}, welcome! Onboarding begins..."

        # Envoi uniquement en message texte
        await message.channel.send(description)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketOnboarding(bot))
