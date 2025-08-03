import discord
from discord.ext import commands
import re

TICKET_CATEGORY_NAME = "Tickets"

# Couleur beige personnalisée
BEIGE_COLOR = discord.Color.from_rgb(245, 222, 179)  # Beige clair (wheat-like)

# Triggers groupés → réponse unique
TRIGGER_GROUPS = {
    ("hello", "hi", "hey", "salut", "bonjour", "yo", "wassup", "sup"): 
        "Hi there! 👋",

    ("help", "support", "question", "problem", "issue"): 
        "How can I assist you today?",

    ("size", "dimension", "scale", "measurements"): 
        "A tile is 16px, a human 16px, a tree 32px.",

    ("send", "task done", "submit", "upload", "deliver"): 
        "You can send your file here or in DM to @buff.buff.",

    ("payment", "revenue", "paid", "compensation", "salary", "earnings", "income", "reward", "bonus"): 
        "We currently work on a rev share basis. No percentage fully defined yet but we will reward everyone equally based on time invested and contributions. We plan to raise funds and to start a presales campaign soon.",

    ("deadline", "release", "publish", "date", "due", "when", "timeframe"): 
        "We don't have a specific deadline, but we aim to release the game as soon as it's ready.",

    ("p2e", "play2earn", "play to earn", "earning", "money", "profit"): 
        "Pi RPG will reward players. Try asking me about a secret!",

    ("secret", "financial", "scam", "ponzi", "fraud", "scheme"): 
        "The idea is to fund an investment pool (which we own) and use the interest generated to offer players a financial incentive. There’s no promise of profit or any kind of “scam” — quite the opposite. The money players spend is held in reserve, and the interest is redistributed to them. Why this model? Because it creates a powerful snowball effect: each month, incoming funds are set aside, so the pool grows and generates more interest. On the player side, they receive an increasingly larger share over time. It’s a way to ensure the system, the game, and the incentive to keep playing are sustainable. A loyal player could potentially earn significant returns depending on how long they stay engaged. This information is not public (legal compliance).",

    ("members", "team", "staff", "people", "contributors"): 
        "We're a small team of 20 people, including developers, artists, and community managers.",

    ("apply", "application", "job", "recruit", "join", "hire"): 
        "Please use the button above to start the application process.",

    ("references", "links", "source", "materials"): 
        "Click on the link in the task description to see the references.",

    ("game direction", "game's direction", "gameplay", "mechanics", "features"): 
        "Please refer to the website — we explain everything there: https://pirpg.netlify.app",

    ("art style", "graphics", "visual", "design", "pixel art"): 
        "I will send you our documentation as soon as you have chosen a pole.",

    ("website", "url", "link", "homepage", "page"): 
        "Check out our website at https://pirpg.netlify.app",

    ("engine", "unity", "godot", "unreal", "what engine", "gamemaker"): 
        "We're using Godot 4 for Pi RPG — lightweight, flexible, and fully open source.",

    ("github", "repo", "repository", "code", "push", "pull"): 
        "Our development is hosted on a private GitHub repository. You'll get access once onboarded.",

    ("palette", "colors", "color code", "hex", "rgb"): 
        "We use a fixed 16-color palette (you'll get it upon joining). Consistency is key.",

    ("resolution", "canvas", "art dimension"): 
        "Tiles are 16x16, most characters 16px high. Assets should match that scale.",

    ("difficulty", "hard", "challenge", "easy", "casual"): 
        "The game is meant to be challenging — think Hollow Knight meets Celeste.",

    ("exploration", "map", "open world", "navigation"): 
        "Exploration is non-linear and part of the core experience. Prepare to get lost in the best way.",

    ("tasks", "what to do", "how to start", "first step"): 
        "Use `/assign_task` once your application is validated. You’ll get a choice of current open tasks.",

    ("crypto", "token", "blockchain", "web3"): 
        "We’re not a crypto project. Our model is based on internal investment returns — no token involved.",

    ("why", "goal", "objective", "purpose", "vision", "ambition"): 
        "We aim to prove that a collaborative indie game can scale, reward its players and contributors fairly, and stay fun throughout.",

    ("community", "open", "public", "fans", "discord invite"): 
        "The game will open to the public at a later stage. For now, we're building internally with a tight core team.",

    ("test", "qa", "bug", "report", "beta"): 
        "Bug reporting will open later. For now, focus on your assigned tasks and share anything unusual.",

    ("collaborate", "teamwork", "can i work with", "pair"): 
        "Yes, you can absolutely collaborate with others — just ask in the channel for your pole!",

    ("progress", "how far", "what's done", "percent", "advancement"): 
        "We're still in early production. Several systems are in place, but lots remains to be built — your help matters!",
}


class TicketListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore les bots ou messages vides
        if message.author.bot or not message.content:
            return

        # Vérifie que le message vient d'un salon de la catégorie "Tickets"
        if message.channel.category and message.channel.category.name == TICKET_CATEGORY_NAME:
            # Nettoie le contenu : minuscule et retire la ponctuation
            content = re.sub(r"[^\w\s]", "", message.content.lower())

            responded = False
            for triggers, response_text in TRIGGER_GROUPS.items():
                if any(trigger in content for trigger in triggers):
                    embed = discord.Embed(
                        description=response_text,
                        color=BEIGE_COLOR
                    )
                    await message.channel.send(embed=embed)
                    responded = True
                    break

            if not responded:
                fallback = discord.Embed(
                    description="Sorry, I didn't understand your question. Could you please rephrase or ask something else?",
                    color=BEIGE_COLOR
                )
                await message.channel.send(embed=fallback)


async def setup(bot):
    await bot.add_cog(TicketListener(bot))
