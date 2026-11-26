import enum


class Role(str, enum.Enum):
    admin = "admin"
    gestionnaire = "gestionnaire"
    lecture_seule = "lecture_seule"


class Couleur(str, enum.Enum):
    rouge = "rouge"
    blanc = "blanc"
    rose = "rose"
    effervescent = "effervescent"


class TypeMouvement(str, enum.Enum):
    entree = "entree"
    sortie = "sortie"
    ajustement = "ajustement"  # quantité signée : écart d'inventaire (+/-)
