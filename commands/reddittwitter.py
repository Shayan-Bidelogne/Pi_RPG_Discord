import os
import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncpraw
import aiohttp
import tempfile

# ================== Config ==================
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
DISCORD_CHANNEL_LIBRARY_ID = int(os.environ.get("DISCORD_CHANNEL_LIBRARY_ID", "1439549538556973106"))

# Subreddits disponibles
SUBREDDITS = ["test", "mySubreddit1", "mySubreddit2"]

# ================== Init Reddit ==================
reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
    user_agent=f"discord:mybot:v1.0 (by u/{REDDIT_USERNAME})",
)

# ================== Cog ==================
class RedditPoster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def clean_label(self, text: str) -> str:
        """Nettoie et tronque à 100 caractères"""
        clean = text.replace("\n", " ").strip()
        return clean[:97] + "..." if len(clean) > 100 else clean

    @app_commands.command(name="reddit", description="Poster un tweet depuis la bibliothèque sur Reddit")
    async def reddit_from_library(self, interaction: discord.Interaction):
        channel = self.bot.get_channel(DISCORD_CHANNEL_LIBRARY_ID)
        if not channel:
            await interaction.response.send_message("❌ Library channel not found.", ephemeral=True)
            return

        messages = [msg async for msg in channel.history(limit=50)]
        if not messages:
            await interaction.response.send_message("❌ No tweets in the library.", ephemeral=True)
            return

        # helper to extract text/media from archived tweet message (supports embed + attachments)
        def extract_message_data(msg):
            text = (msg.content or "").strip()
            image_url = None
            attachment_url = None
            tweet_id = None

            # If message uses an embed (twitter_feed uses embed.description & footer)
            if msg.embeds:
                emb = msg.embeds[0]
                if getattr(emb, "description", None):
                    text = emb.description.strip()
                # image in embed
                if getattr(emb, "image", None) and getattr(emb.image, "url", None):
                    image_url = emb.image.url
                # footer may contain "Tweet ID: <id>"
                if getattr(emb, "footer", None) and getattr(emb.footer, "text", None):
                    footer = emb.footer.text
                    if footer.startswith("Tweet ID:"):
                        tweet_id = footer.split(":", 1)[1].strip()

            # attachments fallback
            if msg.attachments and not image_url:
                att = msg.attachments[0]
                attachment_url = att.url
                # prefer attachment if it's an image
                ct = getattr(att, "content_type", "") or ""
                if ct.startswith("image"):
                    image_url = att.url

            return {
                "text": text or "",
                "image_url": image_url,
                "attachment_url": attachment_url,
                "tweet_id": tweet_id,
            }

        def make_label(msg, idx):
            data = extract_message_data(msg)
            preview = (data["text"] or "").replace("\n", " ").strip()
            if preview:
                preview = self.clean_label(preview)
            elif data["image_url"]:
                preview = "Image"
            elif data["attachment_url"]:
                preview = "Attachment"
            else:
                preview = "[No text]"
            label = f"#{idx+1} — {preview}"
            return label[:100] or "[No text]"

        # ---------- Modal to ask for title ----------
        class TitleModal(ui.Modal):
            def __init__(self, msg, idx):
                super().__init__(title="Enter Reddit post title")
                self.msg = msg
                self.idx = idx
                self.title_input = ui.TextInput(label="Title (max 300 chars)", style=discord.TextStyle.short, max_length=300)
                self.add_item(self.title_input)

            async def on_submit(self, modal_inter: discord.Interaction):
                title = self.title_input.value.strip() or f"Library post #{self.idx+1}"
                await modal_inter.response.send_message("Choose a subreddit:", view=SubredditView(self.msg, self.idx, title), ephemeral=True)

        # ---------- Tweet selection ----------
        class TweetSelect(ui.Select):
            def __init__(self, messages):
                options = [
                    discord.SelectOption(label=make_label(msg, i), value=str(i))
                    for i, msg in enumerate(messages[:25])
                ]
                super().__init__(placeholder="Choose a tweet...", options=options, min_values=1, max_values=1)
                self.messages = messages

            async def callback(self, interaction2: discord.Interaction):
                idx = int(self.values[0])
                msg = self.messages[idx]
                await interaction2.response.send_modal(TitleModal(msg, idx))

        class TweetView(ui.View):
            def __init__(self, messages):
                super().__init__(timeout=120)
                self.add_item(TweetSelect(messages))

        # ---------- Subreddit selection ----------
        class SubredditSelect(ui.Select):
            def __init__(self, msg, idx, title):
                options = [discord.SelectOption(label=sub, value=sub) for sub in SUBREDDITS[:25]]
                super().__init__(placeholder="Choose a subreddit...", options=options, min_values=1, max_values=1)
                self.msg = msg
                self.idx = idx
                self.title = title

            async def callback(self, interaction3: discord.Interaction):
                subreddit_name = self.values[0]
                data = extract_message_data(self.msg)

                embed = discord.Embed(title=self.title[:300], color=discord.Color.blurple())
                if data["text"]:
                    embed.add_field(name="Content", value=data["text"][:1024], inline=False)
                if data["image_url"]:
                    embed.set_image(url=data["image_url"])
                elif data["attachment_url"]:
                    embed.add_field(name="Attachment", value=data["attachment_url"], inline=False)
                embed.set_footer(text=f"Subreddit: r/{subreddit_name}")

                await interaction3.response.send_message("Preview — confirm before posting:", embed=embed, view=ConfirmView(self.msg, self.idx, self.title, subreddit_name), ephemeral=True)

        class SubredditView(ui.View):
            def __init__(self, msg, idx, title):
                super().__init__(timeout=120)
                self.add_item(SubredditSelect(msg, idx, title))

        # ---------- Confirm / Cancel ----------
        class ConfirmView(ui.View):
            def __init__(self, msg, idx, title, subreddit_name):
                super().__init__(timeout=120)
                self.msg = msg
                self.idx = idx
                self.title = title
                self.subreddit_name = subreddit_name

            @ui.button(label="Confirm", style=discord.ButtonStyle.success)
            async def confirm(self, interaction4: discord.Interaction, button: ui.Button):
                await interaction4.response.defer(ephemeral=True)
                try:
                    data = extract_message_data(self.msg)
                    subreddit_obj = await reddit.subreddit(self.subreddit_name, fetch=True)
                    submission = None

                    # If we have an image URL (from embed or attachment), download and post image
                    media_url = data["image_url"] or data["attachment_url"]
                    if media_url:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(media_url) as resp:
                                if resp.status == 200:
                                    suffix = ".mp4" if media_url.endswith(".mp4") else None
                                    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                                    tmp_file.write(await resp.read())
                                    tmp_file.close()
                                    try:
                                        if suffix is None:
                                            submission = await subreddit_obj.submit_image(title=self.title[:300], image_path=tmp_file.name)
                                        else:
                                            submission = await subreddit_obj.submit_video(title=self.title[:300], video_path=tmp_file.name)
                                    finally:
                                        try:
                                            os.unlink(tmp_file.name)
                                        except Exception:
                                            pass
                                else:
                                    await interaction4.followup.send("❌ Failed to download attachment.", ephemeral=True)
                                    return
                    else:
                        submission = await subreddit_obj.submit(title=self.title[:300], selftext=(data["text"] or ""))

                    if submission is not None:
                        try:
                            await submission.load()
                        except Exception:
                            pass
                        permalink = getattr(submission, "permalink", None)
                        post_url = f"https://reddit.com{permalink}" if permalink else f"https://reddit.com/comments/{getattr(submission, 'id', '')}"
                        await interaction4.followup.send(f"✅ Reddit post published: {post_url}", ephemeral=True)
                    else:
                        await interaction4.followup.send("❌ Unable to obtain submission object.", ephemeral=True)
                except Exception as e:
                    await interaction4.followup.send(f"❌ Reddit error: {e}", ephemeral=True)

            @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
            async def cancel(self, interaction4: discord.Interaction, button: ui.Button):
                await interaction4.response.send_message("Cancelled.", ephemeral=True)

        await interaction.response.send_message("📚 Select a tweet from the library:", view=TweetView(messages), ephemeral=True)


async def setup(bot):
    await bot.add_cog(RedditPoster(bot))
