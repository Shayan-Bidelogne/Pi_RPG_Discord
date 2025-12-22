"""Configuration dédiée à la modération automatique et aux réponses automatiques."""
from typing import Dict, List
from config import AUTHORIZED_ROLE_ID

# Liste des rôles (IDs) auxquels la modération s'applique
# Remplacez par les IDs voulus (ex: [123456789012345678])
MOD_ROLE_IDS: List[int] = [AUTHORIZED_ROLE_ID]

# Comportement de modération
MOD_BLOCK_MENTIONS: bool = True
MOD_BLOCK_LINKS: bool = True

# Mots/phrases interdits (suppressions automatiques)
MOD_BANNED_WORDS: List[str] = [
    "badword1",
    "badword2",
]

# Message d'avertissement post-suppression (affiché brièvement)
MOD_WARNING_MESSAGE: str = "Auto-mod {user}! ❌"

# --- Réponses automatiques ---
# Mapping simple : déclencheur (chaîne) -> réponse (chaîne)
# Le déclencheur est cherché dans le message (sensible à la casse selon
# AUTO_RESPONSES_CASE_SENSITIVE). Vous pouvez utiliser des clés courtes
# ou des phrases complètes.
AUTO_RESPONSE_GROUPS = {
    "greetings": {
        "triggers": ["bonjour", "salut", "hello", "hi", "hey"],
        "responses": [
            "Hi {user} !",
            "Hello {user}",
            "Hey {user} — how are you?",
        ],
        "target_role_ids": [],
        "case_sensitive": False,
        "daily_limit": 1,
    },
    "investment": {
        "triggers": ["investment", "cryptocurrency", "money"],
        "responses": [
            "{user}, Pi RPG is a game not an investment",
            "{user}, we're not providing any financial advice!",
        ],
        "target_role_ids": [],
        "case_sensitive": False,
        "daily_limit": 1,
    },
}

# Si vide => appliqué à tous; sinon liste de role IDs contraignant l'application
AUTO_RESPONSES_TARGET_ROLE_IDS: List[int] = []

# Contrôle de la sensibilité à la casse pour la détection
AUTO_RESPONSES_CASE_SENSITIVE: bool = False

# Si True, la réponse mentionnera l'utilisateur (en utilisant '{user}' dans la valeur)
# Les réponses peuvent contenir le placeholder '{user}' qui sera remplacé
# par la mention de l'auteur.
AUTO_RESPONSE_STATE_FILE = "data/auto_response_state.json"
