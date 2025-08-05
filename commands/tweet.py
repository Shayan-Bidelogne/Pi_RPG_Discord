import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import os
import json

# Dossiers de stockage
TWEET_LOG_FOLDER = 'scheduled_tweets/'
VALIDATED_TWEET_FOLDER = 'validated_tweets/'
TWEET_CHANNEL_ID = 1367610016147706047  # À adapter à ton salon

for folder in [TWEET_LOG_FOLDER, VALIDATED_TWEET_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Classe du bouton
class TweetLinkView(discord.ui.View):
    def __init__(self, link: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Copier le lien Twitter", url=link))

# Commandes
async def setup(bot):
    # Soumettre un tweet
    @bot.tree.command(name="submit_tweet", description="Soumettre un tweet pour validation")
    @app_commands.describe(message="Contenu du tweet", date_time="Date de publication souhaitée")
    @app_commands.autocomplete(date_time=autocomplete_dates)
    async def submit_tweet(interaction: discord.Interaction, message: str, date_time: str):
        try:
            publish_time = datetime.strptime(date_time, "%Y-%m-%d %H:%M")

            tweet_data = {
                "message": message,
                "publish_time": publish_time.strftime('%Y-%m-%d %H:%M')
            }

            tweet_id = publish_time.strftime('%Y-%m-%d_%H-%M')
            path = os.path.join(TWEET_LOG_FOLDER, f"{tweet_id}_tweet.json")
            with open(path, 'w') as f:
                json.dump(tweet_data, f)

            embed = discord.Embed(title="Tweet à valider", description=message, color=discord.Color.orange())
            embed.add_field(name="Date prévue", value=publish_time.strftime('%Y-%m-%d %H:%M'))
            embed.set_footer(text=f"ID: {tweet_id}")

            await interaction.response.send_message(f"Tweet enregistré pour validation.")
        except Exception as e:
            await interaction.response.send_message(f"Erreur : {e}")

    # Valider un tweet
    @bot.tree.command(name="validate_tweet", description="Valider un tweet (admin uniquement)")
    @app_commands.describe(tweet_id="ID du tweet soumis")
    @app_commands.autocomplete(tweet_id=suggest_tweet_ids)
    async def validate_tweet(interaction: discord.Interaction, tweet_id: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Permission refusée.", ephemeral=True)
            return

        try:
            path = os.path.join(TWEET_LOG_FOLDER, f"{tweet_id}_tweet.json")
            with open(path, 'r') as f:
                tweet_data = json.load(f)

            new_path = os.path.join(VALIDATED_TWEET_FOLDER, f"{tweet_id}_tweet.json")
            os.rename(path, new_path)

            embed = discord.Embed(title="Tweet validé", description=tweet_data['message'], color=discord.Color.green())
            embed.add_field(name="À poster manuellement à :", value=tweet_data['publish_time'])
            embed.set_footer(text=f"ID: {tweet_id}")

            # Créer la vue avec bouton
            tweet_channel = bot.get_channel(TWEET_CHANNEL_ID)
            view = TweetLinkView(link="https://twitter.com/intent/tweet")  # à personnaliser si besoin
            await tweet_channel.send(embed=embed, view=view)

            await interaction.response.send_message(f"✅ Tweet validé et posté dans le canal.")
        except FileNotFoundError:
            await interaction.response.send_message("Tweet introuvable.")
        except Exception as e:
            await interaction.response.send_message(f"Erreur : {e}")

# Autocomplétion de l’ID
async def suggest_tweet_ids(interaction: discord.Interaction, current: str):
    tweet_files = [f for f in os.listdir(TWEET_LOG_FOLDER) if f.endswith('_tweet.json')]
    tweet_ids = [f.replace('_tweet.json', '') for f in tweet_files]
    return [app_commands.Choice(name=tid, value=tid) for tid in tweet_ids if current in tid]

# Autocomplétion des dates
async def autocomplete_dates(interaction: discord.Interaction, current: str):
    now = datetime.now()
    return [
        app_commands.Choice(
            name=(d := (now + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M')),
            value=d
        )
        for i in range(25) if current in (now + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M')
    ]
