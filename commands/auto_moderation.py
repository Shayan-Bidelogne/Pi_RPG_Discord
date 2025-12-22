import re
import os
import json
import random
from datetime import date

import discord
from discord.ext import commands
from config_moderation import (
    MOD_ROLE_IDS,
    MOD_BANNED_WORDS,
    MOD_BLOCK_LINKS,
    MOD_BLOCK_MENTIONS,
    MOD_WARNING_MESSAGE,
    AUTO_RESPONSE_GROUPS,
    AUTO_RESPONSE_STATE_FILE,
)


class AutoModeration(commands.Cog):
    """Cog d'auto-modération : bloque mentions, liens, mots interdits pour certains rôles,
    et gère des réponses automatiques groupées avec quota journalier.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.link_regex = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
        # State pour quotas journaliers
        self._state_file = AUTO_RESPONSE_STATE_FILE
        self._state = self._load_state()

    def _author_has_monitored_role(self, member: discord.Member) -> bool:
        try:
            author_roles = {r.id for r in member.roles}
            return any(rid in author_roles for rid in MOD_ROLE_IDS)
        except Exception:
            return False

    def _author_in_group_targets(self, member: discord.Member, target_ids) -> bool:
        if not target_ids:
            return True
        try:
            author_roles = {r.id for r in member.roles}
            return any(rid in author_roles for rid in target_ids)
        except Exception:
            return False

    def _load_state(self):
        try:
            folder = os.path.dirname(self._state_file)
            if folder and not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            if not os.path.exists(self._state_file):
                return {}
            with open(self._state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self):
        try:
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            return

        content = message.content or ""

        # --- Modération (s'applique uniquement si l'auteur a un rôle surveillé) ---
        if self._author_has_monitored_role(message.author):
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

        # --- Réponses automatiques par groupes ---
        if not AUTO_RESPONSE_GROUPS:
            return

        for group_name, cfg in AUTO_RESPONSE_GROUPS.items():
            triggers = cfg.get("triggers", [])
            responses = cfg.get("responses", [])
            target_role_ids = cfg.get("target_role_ids", [])
            case_sensitive = cfg.get("case_sensitive", False)
            daily_limit = cfg.get("daily_limit", 1) or 1

            # Vérifier cible de rôle pour ce groupe
            if not self._author_in_group_targets(message.author, target_role_ids):
                continue

            check_text = content if case_sensitive else content.lower()

            matched = False
            for trig in triggers:
                if not trig:
                    continue
                t = trig if case_sensitive else trig.lower()
                if t in check_text:
                    matched = True
                    break

            if not matched:
                continue

            # Vérifier quota quotidien pour (group, user)
            uid = str(message.author.id)
            today = date.today().isoformat()
            group_state = self._state.get(group_name, {})
            last = group_state.get(uid)
            if last == today:
                # déjà répondu aujourd'hui pour ce groupe
                continue

            # Envoyer une réponse aléatoire
            if not responses:
                continue
            resp = random.choice(responses)
            formatted = resp.replace("{user}", message.author.mention)
            try:
                await message.channel.send(formatted)
            except Exception:
                pass

            # Mettre à jour l'état
            if group_name not in self._state:
                self._state[group_name] = {}
            self._state[group_name][uid] = today
            self._save_state()
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoModeration(bot))
