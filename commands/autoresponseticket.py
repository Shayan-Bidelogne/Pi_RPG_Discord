import discord
from discord.ext import commands

# Nom de la catégorie à surveiller
TICKET_CATEGORY_NAME = "Tickets"

# Triggers -> réponses automatiques
TRIGGERS = {
    "hello": "Hi there! 👋",
    "help": "How can I assist you today?",
    "apply": "Please use the button above to start the application process.",
}

class TicketListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorer les messages du bot
        if message.author.bot:
            return

        # Vérifie que le message provient d'un channel dans la catégorie "Tickets"
        if message.channel.category and message.channel.category.name == TICKET_CATEGORY_NAME:
            content = message.content.lower()

            # Parcourt tous les triggers définis
            for trigger, response in TRIGGERS.items():
                if trigger in content:
                    await message.channel.send(response)
                    break  # On ne répond qu'une seule fois par message

async def setup(bot):
    await bot.add_cog(TicketListener(bot))
