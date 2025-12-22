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
MOD_WARNING_MESSAGE: str = "Votre message a été supprimé par la modération automatique."

# --- Réponses automatiques ---
# Mapping simple : déclencheur (chaîne) -> réponse (chaîne)
# Le déclencheur est cherché dans le message (sensible à la casse selon
# AUTO_RESPONSES_CASE_SENSITIVE). Vous pouvez utiliser des clés courtes
# ou des phrases complètes.
AUTO_RESPONSES: Dict[str, str] = {
    "bonjour": "Bonjour {user}, bienvenue !",
    "aide": "Si vous avez besoin d'aide, consultez le channel #support ou répondez ici.",
}

# Si vide => appliqué à tous; sinon liste de role IDs contraignant l'application
AUTO_RESPONSES_TARGET_ROLE_IDS: List[int] = []

# Contrôle de la sensibilité à la casse pour la détection
AUTO_RESPONSES_CASE_SENSITIVE: bool = False

# Si True, la réponse mentionnera l'utilisateur (en utilisant '{user}' dans la valeur)
# Les réponses peuvent contenir le placeholder '{user}' qui sera remplacé
# par la mention de l'auteur.
