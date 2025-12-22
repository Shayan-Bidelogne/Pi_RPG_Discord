import re
import discord
from discord.ext import commands
from config_moderation import (
    MOD_ROLE_IDS,
    MOD_BANNED_WORDS,
    MOD_BLOCK_LINKS,
    MOD_BLOCK_MENTIONS,
    MOD_WARNING_MESSAGE,
    AUTO_RESPONSES,
    AUTO_RESPONSES_CASE_SENSITIVE,
    AUTO_RESPONSES_TARGET_ROLE_IDS,
)


class AutoModeration(commands.Cog):
    """Cog d'auto-modération : bloque mentions, liens, mots interdits pour certains rôles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.link_regex = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
        # Prépare triggers en fonction de la sensibilité
        if AUTO_RESPONSES_CASE_SENSITIVE:
            self._auto_triggers = {k: v for k, v in AUTO_RESPONSES.items()}
        else:
            self._auto_triggers = {k.lower(): v for k, v in AUTO_RESPONSES.items()}

    def _author_has_monitored_role(self, member: discord.Member) -> bool:
        try:
            author_roles = {r.id for r in member.roles}
            return any(rid in author_roles for rid in MOD_ROLE_IDS)
        except Exception:
            return False

    def _author_in_auto_targets(self, member: discord.Member) -> bool:
        if not AUTO_RESPONSES_TARGET_ROLE_IDS:
            return True
        try:
            author_roles = {r.id for r in member.roles}
            return any(rid in author_roles for rid in AUTO_RESPONSES_TARGET_ROLE_IDS)
        except Exception:
            return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            return

        if not self._author_has_monitored_role(message.author):
            return

        content = message.content or ""

        # Mentions (users / roles / everyone)
        if MOD_BLOCK_MENTIONS:
            if message.mentions or message.raw_role_mentions or message.mention_everyone:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    await message.channel.send(f"{message.author.mention} {MOD_WARNING_MESSAGE}", delete_after=5)
                except Exception:
                    pass
                return

        # Liens
        if MOD_BLOCK_LINKS and self.link_regex.search(content):
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.channel.send(f"{message.author.mention} {MOD_WARNING_MESSAGE}", delete_after=5)
            except Exception:
                pass
            return

        # Mots interdits
        text_lower = content.lower()
        for banned in MOD_BANNED_WORDS:
            if banned and banned.lower() in text_lower:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    await message.channel.send(f"{message.author.mention} {MOD_WARNING_MESSAGE}", delete_after=5)
                except Exception:
                    pass
                return

        # Réponses automatiques (appliquer seulement si l'auteur est dans la cible)
        if AUTO_RESPONSES and self._author_in_auto_targets(message.author):
            check_text = content if AUTO_RESPONSES_CASE_SENSITIVE else content.lower()
            for trigger, response in self._auto_triggers.items():
                if trigger and trigger in check_text:
                    try:
                        # Support du placeholder {user}
                        formatted = response.replace("{user}", message.author.mention)
                        await message.channel.send(formatted)
                    except Exception:
                        pass
                    return


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoModeration(bot))
