import discord
from discord import app_commands
from discord.ext import commands
from requests_oauthlib import OAuth1Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import os
import json

# Twitter API Keys
consumer_key = 'ycTKrPWu2SpGX8hYGmaoJHJfF'
consumer_secret = 'cHKq4HykkB7Tdh7whpspPdTkWcPAOI29CJvLgU2zMeK06slnuR'
access_token = '1916507677888577536-SkDsMWbKVQHiqRYvYt6nVYueqeusGa'
access_token_secret = 'al59aLf4pkaDrSIdSsfNHX9pSp3Pg2QRsEBy0P7KDd9bl'

# Create OAuth session with the keys
oauth = OAuth1Session(consumer_key, consumer_secret, access_token, access_token_secret)

# API URL to post a tweet
url = "https://api.x.com/2/tweets"

# Scheduler initialization
scheduler = AsyncIOScheduler()

# Local folder to store scheduled tweets
TWEET_LOG_FOLDER = 'scheduled_tweets/'
if not os.path.exists(TWEET_LOG_FOLDER):
    os.makedirs(TWEET_LOG_FOLDER)

# Folder for validated tweets
VALIDATED_TWEET_FOLDER = 'validated_tweets/'
if not os.path.exists(VALIDATED_TWEET_FOLDER):
    os.makedirs(VALIDATED_TWEET_FOLDER)

# Folder for posted tweets
POSTED_TWEET_FOLDER = 'posted_tweets/'
if not os.path.exists(POSTED_TWEET_FOLDER):
    os.makedirs(POSTED_TWEET_FOLDER)

# Channel where tweets will be submitted
TWEET_CHANNEL_ID = 1367610016147706047  # Replace with actual channel ID

# Function to send the tweet
def post_tweet(message, tweet_id):
    tweet = {"text": message}
    try:
        # Send POST request to publish a tweet
        response = oauth.post(url, json=tweet)
        
        # Check the API response
        if response.status_code == 201:
            print("Tweet successfully posted!")

            # Move the file from validated_tweets to posted_tweets after successful post
            validated_tweet_path = os.path.join(VALIDATED_TWEET_FOLDER, f"{tweet_id}_tweet.json")
            posted_tweet_path = os.path.join(POSTED_TWEET_FOLDER, f"{tweet_id}_tweet.json")
            os.rename(validated_tweet_path, posted_tweet_path)
            
        else:
            print(f"Error while sending the tweet: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"Error while sending the tweet: {e}")

# Function to automatically schedule validated tweets on bot startup
async def schedule_validated_tweets():
    validated_tweet_folder = 'validated_tweets/'
    if not os.path.exists(validated_tweet_folder):
        return
    
    # Retrieve all the validated tweet files
    tweet_files = [f for f in os.listdir(validated_tweet_folder) if f.endswith('_tweet.json')]

    for tweet_file in tweet_files:
        tweet_id = tweet_file.split('_')[0]  # Extract the tweet ID
        tweet_log_path = os.path.join(validated_tweet_folder, tweet_file)
        
        try:
            # Read the tweet data from file
            with open(tweet_log_path, 'r') as log_file:
                tweet_data = json.load(log_file)
            
            # Convert the publish time to a datetime object
            publish_time = datetime.strptime(tweet_data['publish_time'], '%Y-%m-%d %H:%M')

            # Define the function to post the tweet
            def schedule_post():
                post_tweet(tweet_data['message'], tweet_id)

            # Add the tweet to the scheduler
            scheduler.add_job(schedule_post, 'date', run_date=publish_time, id=tweet_id)

            # Start the scheduler if not already running
            if not scheduler.running:
                scheduler.start()

            print(f"✅ Tweet {tweet_id} scheduled for {publish_time.strftime('%Y-%m-%d %H:%M')}.")

        except Exception as e:
            print(f"⚠️ Failed to schedule tweet {tweet_id}: {e}")

# Command definition
async def setup(bot):
    # Submit a tweet for review
    @bot.tree.command(name="submit_tweet", description="Submit a tweet to be scheduled")
    @app_commands.describe(message="Tweet content", date_time="Tweet publication date and time")
    @app_commands.autocomplete(date_time=autocomplete_dates)
    async def submit_tweet(interaction: discord.Interaction, message: str, date_time: str):
        try:
            # Convert the date and time into a datetime object
            publish_time = datetime.strptime(date_time, "%Y-%m-%d %H:%M")
            
            # Save the tweet in a local file
            tweet_data = {
                "message": message,
                "publish_time": publish_time.strftime('%Y-%m-%d %H:%M')
            }
            tweet_log_path = os.path.join(TWEET_LOG_FOLDER, f"{publish_time.strftime('%Y-%m-%d_%H-%M')}_tweet.json")
            with open(tweet_log_path, 'w') as log_file:
                json.dump(tweet_data, log_file)

            # Create an embed for the tweet
            embed = discord.Embed(title="Tweet to be scheduled", description=message, color=discord.Color.blue())
            embed.add_field(name="Publish Date", value=publish_time.strftime('%Y-%m-%d %H:%M'))
            embed.set_footer(text=f"ID: {publish_time.strftime('%Y-%m-%d_%H-%M')}")

            # Send the embed to a specific channel
            tweet_channel = bot.get_channel(TWEET_CHANNEL_ID)
            await tweet_channel.send(embed=embed)

            # Respond to the user
            await interaction.response.send_message(f"Tweet submitted for validation. It will be posted on {publish_time.strftime('%Y-%m-%d %H:%M')}.")
        except ValueError:
            await interaction.response.send_message("Invalid date format. Use 'YYYY-MM-DD HH:MM'.")
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}")

    # Validate and schedule a tweet (admin-only)
    @bot.tree.command(name="validate_tweet", description="Validate and schedule a tweet")
    @app_commands.describe(tweet_id="Submitted tweet ID")
    @app_commands.autocomplete(tweet_id=suggest_tweet_ids)  # Add autocomplete here for tweet_id
    async def validate_tweet(interaction: discord.Interaction, tweet_id: str):
        # Check if the user is an administrator
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You need to be an administrator to use this command.")
            return

        try:
            # Load the file of the submitted tweet
            tweet_log_path = os.path.join(TWEET_LOG_FOLDER, f"{tweet_id}_tweet.json")
            with open(tweet_log_path, 'r') as log_file:
                tweet_data = json.load(log_file)
            
            # Convert the publish date and time
            publish_time = datetime.strptime(tweet_data['publish_time'], '%Y-%m-%d %H:%M')

            # Function to send the tweet
            def schedule_post():
                post_tweet(tweet_data['message'], tweet_id)

            # Add the task to the scheduler for execution at the scheduled time
            scheduler.add_job(schedule_post, 'date', run_date=publish_time)

            # Start the scheduler if it's not already running
            if not scheduler.running:
                scheduler.start()

            # Move the validated tweet to the 'validated_tweets' folder
            new_tweet_log_path = os.path.join(VALIDATED_TWEET_FOLDER, f"{tweet_id}_tweet.json")
            os.rename(tweet_log_path, new_tweet_log_path)

            # Respond to the user that the task has been validated and the tweet is moved
            await interaction.response.send_message(f"Tweet validated and scheduled for {publish_time.strftime('%Y-%m-%d %H:%M')}. It has been moved to the validated folder.")
        except FileNotFoundError:
            await interaction.response.send_message(f"No tweet found with the ID {tweet_id}.")
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}")

    # Commande pour voir les jobs programmés
    @bot.tree.command(name="scheduled_tweets", description="Affiche les tweets programmés")
    async def scheduled_tweets(interaction: discord.Interaction):
        # Récupère tous les jobs planifiés
        jobs = scheduler.get_jobs()

        if not jobs:
            await interaction.response.send_message("Aucun tweet n'est actuellement programmé.")
            return

        # Crée un embed pour afficher les jobs
        embed = discord.Embed(title="Tweets programmés", color=discord.Color.green())
        for job in jobs:
            tweet_id = job.id
            run_time = job.next_run_time.strftime('%Y-%m-%d %H:%M')
            embed.add_field(name=f"Tweet ID: {tweet_id}", value=f"Publié le: {run_time}", inline=False)
    
        await interaction.response.send_message(embed=embed)

# Fonction pour l'auto-complétion des ID de tweet
async def suggest_tweet_ids(interaction: discord.Interaction, current: str):
    tweet_files = [f for f in os.listdir(TWEET_LOG_FOLDER) if f.endswith('_tweet.json')]
    tweet_ids = [file.split('_')[0] + "_" + file.split('_')[1] for file in tweet_files]  # Ajout de l'heure à l'ID
    
    # Inclure l'ID complet avec la date et l'heure
    return [app_commands.Choice(name=f"{tweet_id}", value=f"{tweet_id}") for tweet_id in tweet_ids if current.lower() in tweet_id.lower()]


async def autocomplete_dates(interaction: discord.Interaction, current: str):
    # Current date/time
    now = datetime.now()
    suggestions = []

    # Generate date suggestions for the next 25 hours, every hour
    for i in range(25):  # 25 suggests: current hour + 24 hours ahead
        suggestion_date = now + timedelta(hours=i)
        date_suggestion = suggestion_date.strftime('%Y-%m-%d %H:%M')
        if current.lower() in date_suggestion.lower():
            suggestions.append(app_commands.Choice(name=date_suggestion, value=date_suggestion))

    return suggestions

# Ensure to call this function when the bot starts
async def on_ready():
    print("Bot is online and starting the scheduling system...")
    await schedule_validated_tweets()
    scheduler.start()
