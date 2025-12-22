# config.py
AUTHORIZED_ROLE_ID = 1354459284020134089
TOKEN = "your-token-here"
GUILD_ID = 1354455462514262157
TASKS_CHANNEL_ID = {
    'pixel_art': 1355852568806293637,
    'marketing': 1401139679423631430,
    'programmation': 1363812990566006865,
    'animation': 1401647416993906699,
}
CARDS = ["None", "Village", "Forest", "Crystal Forest"]

# --- Modération automatique ---
# Liste des rôles (IDs) auxquels la modération s'applique
MOD_ROLE_IDS = [AUTHORIZED_ROLE_ID]

# Comportement de modération (True = bloqué)
MOD_BLOCK_MENTIONS = True
MOD_BLOCK_LINKS = True

# Mots/phrases interdits (suppressions automatiques)
MOD_BANNED_WORDS = [
    "badword1",
    "badword2",
]

# Message d'avertissement post-suppression (affiché brièvement)
MOD_WARNING_MESSAGE = "Votre message a été supprimé par la modération automatique."
