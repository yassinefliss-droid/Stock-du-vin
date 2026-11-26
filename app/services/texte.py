import re
import unicodedata


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, ponctuation → espaces. « Saint-Émilion » → « saint emilion »."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sans_accents.lower()).strip()
