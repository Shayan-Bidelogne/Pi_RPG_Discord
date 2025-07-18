import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image
import os
import aiohttp

TILESET_PATH = "tileset.png"
MAX_WIDTH = 480


def extraire_tuiles(tileset: Image.Image, tuile_size: tuple[int, int]) -> list[Image.Image]:
    """Extrait toutes les tuiles d’un tileset existant."""
    tw, th = tileset.size
    nw, nh = tuile_size
    tuiles = []

    for y in range(0, th, nh):
        for x in range(0, tw, nw):
            tuile = tileset.crop((x, y, x + nw, y + nh))
            if tuile.getbbox():  # Ignore les tuiles vides
                tuiles.append(tuile)

    return tuiles


def organiser_tuiles_par_lignes(tuiles: list[Image.Image], largeur_max: int) -> list[tuple[list[Image.Image], int]]:
    """Organise les tuiles en lignes, selon la largeur maximale autorisée."""
    lignes = []
    ligne_actuelle = []
    largeur_actuelle = 0
    hauteur_max = 0

    for tuile in tuiles:
        w, h = tuile.size
        if largeur_actuelle + w > largeur_max:
            lignes.append((ligne_actuelle, hauteur_max))
            ligne_actuelle = [tuile]
            largeur_actuelle = w
            hauteur_max = h
        else:
            ligne_actuelle.append(tuile)
            largeur_actuelle += w
            hauteur_max = max(hauteur_max, h)

    if ligne_actuelle:
        lignes.append((ligne_actuelle, hauteur_max))

    return lignes


def construire_tileset_depuis_lignes(lignes: list[tuple[list[Image.Image], int]], largeur_max: int) -> Image.Image:
    """Construit le tileset final à partir des lignes de tuiles."""
    hauteur_totale = sum(h for _, h in lignes)
    nouveau_tileset = Image.new("RGBA", (largeur_max, hauteur_totale), (0, 0, 0, 0))

    y = 0
    for ligne, hauteur in lignes:
        x = 0
        for tuile in ligne:
            nouveau_tileset.paste(tuile, (x, y))
            x += tuile.width
        y += hauteur

    return nouveau_tileset


def ajouter_tuile_au_tileset(nouvelle_tuile_path, tileset_path=TILESET_PATH, largeur_max=MAX_WIDTH):
    """Ajoute une nouvelle tuile à un tileset existant ou en crée un nouveau."""
    nouvelle_tuile = Image.open(nouvelle_tuile_path).convert("RGBA")
    tuile_size = nouvelle_tuile.size

    if os.path.exists(tileset_path):
        tileset = Image.open(tileset_path).convert("RGBA")
        tuiles = extraire_tuiles(tileset, tuile_size)
    else:
        tuiles = []

    tuiles.append(nouvelle_tuile)
    lignes = organiser_tuiles_par_lignes(tuiles, largeur_max)
    nouveau_tileset = construire_tileset_depuis_lignes(lignes, largeur_max)
    nouveau_tileset.save(tileset_path)

    return tileset_path


@discord.app_commands.command(name="tileset", description="Ajoute une image au tileset.")
async def tileset(interaction: discord.Interaction, image: discord.Attachment):
    await interaction.response.defer(thinking=True)

    if not image.content_type or not image.content_type.startswith("image/"):
        await interaction.followup.send("❌ Le fichier fourni n'est pas une image.")
        return

    temp_path = f"temp_{image.filename}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image.url) as resp:
                if resp.status != 200:
                    await interaction.followup.send("❌ Impossible de télécharger l'image.")
                    return
                with open(temp_path, "wb") as f:
                    f.write(await resp.read())

        output_path = ajouter_tuile_au_tileset(temp_path)
        await interaction.followup.send(
            content="✅ Tuile ajoutée au tileset !",
            file=discord.File(output_path)
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Une erreur est survenue : {e}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# Setup pour load_extension
async def setup(bot: commands.Bot):
    bot.tree.add_command(tileset)
