import discord
from discord.ext import commands

# IDs des rôles utilisés comme trigger (pas pour attribution)
ROLE_IDS = {
    "pixel_artist": 1401139679423631430,
    "dev": 1363812990566006865,
    "marketing": 1401139679423631430,
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
            description = "🎨 You chose Pixel Artist! Let's start with portfolio questions..."
        elif chosen_role == "dev":
            description = "💻 You chose Developer! We'll start with coding questions..."
        elif chosen_role == "marketing":
            description = "📣 You chose Marketing! Let's talk about social media strategy..."
        else:
            description = "Welcome! Onboarding begins..."

        embed = discord.Embed(
            title="Pi RPG Onboarding",
            description=description,
            color=0x00FF00
        )

        await message.channel.send(
            f"✅ {message.author.mention} started onboarding for **{chosen_role.replace('_',' ').title()}**!",
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketOnboarding(bot))
