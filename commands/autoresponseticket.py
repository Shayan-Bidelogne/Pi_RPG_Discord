import discord
from discord.ext import commands

TICKET_CATEGORY_NAME = "Tickets"

# Triggers groupés → réponse unique
TRIGGER_GROUPS = {
    ("hello",): "Hi there! 👋",
    ("help",): "How can I assist you today?",
    ("size",): "A tile is 16px, a human 16px, a tree 32px",
    ("send",): "You can send your file here or in the application DM",
    ("payment", "revenue", "paid"): "We currently work on a rev share basis. Let us know if you have questions!",
    ("deadline", "release", "publish"): "We don't have a specific deadline, but we aim to release the game as soon as it's ready.",
    ("p2e", "play2earn", "play to earn"): "Pi RPG will reward players try asking me about a secret",
    ("secret", "financial"): "We plan to invest game revenue into real world assets, like real estate, to generate income for the p2e model",
    ("apply",): "Please use the button above to start the application process.",
}

class TicketListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Vérifie que le message vient d'un salon dans la bonne catégorie
        if message.channel.category and message.channel.category.name == TICKET_CATEGORY_NAME:
            content = message.content.lower()

            # Recherche dans chaque groupe de mots-clés
            for triggers, response in TRIGGER_GROUPS.items():
                if any(trigger in content for trigger in triggers):
                    await message.channel.send(response)
                    break  # Répond une seule fois
                

async def setup(bot):
    await bot.add_cog(TicketListener(bot))
