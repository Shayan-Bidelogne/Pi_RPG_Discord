import re
import discord
from discord.ext import commands
from config import (
    GUILD_ID,
    MOD_ROLE_IDS,
    MOD_BLOCK_MENTIONS,
    MOD_BLOCK_LINKS,
    MOD_BANNED_WORDS,
    MOD_WARNING_MESSAGE,
)

MENTION_REGEX = re.compile(
    r"<@!?(\d+)>|<@&(\d+)>|@everyone|@here",
    re.IGNORECASE
)

LINK_REGEX = re.compile(
    r"https?://\S+|www\.\S+",
    re.IGNORECASE
)


class AutoModeration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ───────────────────────────────
    # Utils
    # ───────────────────────────────

    def _has_monitored_role(self, member: discord.Member) -> bool:
        return any(role.id in MOD_ROLE_IDS for role in member.roles)

    async def _delete_and_warn(self, message: discord.Message):
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            return

        try:
            await message.channel.send(
                f"{message.author.mention} {MOD_WARNING_MESSAGE}",
                delete_after=5
            )
        except discord.Forbidden:
            pass

    # ───────────────────────────────
    # Détections
    # ───────────────────────────────

    def _contains_mention(self, message: discord.Message) -> bool:
        content = message.content or ""

        if MENTION_REGEX.search(content):
            return True

        for embed in message.embeds:
            if embed.title and MENTION_REGEX.search(embed.title):
                return True
            if embed.description and MENTION_REGEX.search(embed.description):
                return True
            if embed.footer and embed.footer.text and MENTION_REGEX.search(embed.footer.text):
                return True

        return False

    def _contains_link(self, message: discord.Message) -> bool:
        content = message.content or ""

        if LINK_REGEX.search(content):
            return True

        for embed in message.embeds:
            if embed.url and LINK_REGEX.search(embed.url):
                return True
            if embed.description and LINK_REGEX.search(embed.description):
                return True

        return False

    def _contains_banned_word(self, message: discord.Message) -> bool:
        content = (message.content or "").lower()
        return any(
            word.lower() in content
            for word in MOD_BANNED_WORDS
            if word
        )

    # ───────────────────────────────
    # Listener principal
    # ───────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

        # Message déjà bloqué par Discord AutoMod
        if message.flags.auto_moderation_action:
            return

        # Webhooks = supprimés direct
        if message.webhook_id is not None:
            await self._delete_and_warn(message)
            return

        if not isinstance(message.author, discord.Member):
            return

        if not self._has_monitored_role(message.author):
            return

        # Mentions
        if MOD_BLOCK_MENTIONS and self._contains_mention(message):
            await self._delete_and_warn(message)
            return

        # Liens
        if MOD_BLOCK_LINKS and self._contains_link(message):
            await self._delete_and_warn(message)
            return

        # Mots interdits
        if self._contains_banned_word(message):
            await self._delete_and_warn(message)
            return

    # ───────────────────────────────
    # AutoMod Discord natif (sync)
    # ───────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        rules = await guild.fetch_auto_moderation_rules()

        if any(r.name == "Block Mentions (Synced)" for r in rules):
            return

        await guild.create_auto_moderation_rule(
            name="Block Mentions (Synced)",
            event_type=discord.AutoModerationEventType.message_send,
            trigger_type=discord.AutoModerationTriggerType.mention_spam,
            trigger_metadata=discord.AutoModerationTriggerMetadata(
                mention_total_limit=1
            ),
            actions=[
                discord.AutoModerationAction(
                    type=discord.AutoModerationActionType.block_message,
                    metadata=discord.AutoModerationActionMetadata(
                        custom_message=MOD_WARNING_MESSAGE
                    )
                )
            ],
            enabled=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoModeration(bot))
