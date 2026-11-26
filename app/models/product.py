from decimal import Decimal

from sqlalchemy import Enum, Numeric, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import Couleur
from app.services.texte import normaliser


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    nom: Mapped[str] = mapped_column(String(200))
    domaine: Mapped[str] = mapped_column(String(200))
    appellation: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(80))
    millesime: Mapped[int | None] = mapped_column(index=True)  # None = non millésimé
    couleur: Mapped[Couleur] = mapped_column(Enum(Couleur, native_enum=False, length=20))
    format: Mapped[str] = mapped_column(String(20), default="75cl")
    prix_achat: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    prix_vente: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    seuil_alerte: Mapped[int] = mapped_column(default=6)
    # Texte normalisé (sans accents, minuscules) pour une recherche indépendante de la base.
    search_text: Mapped[str] = mapped_column(String(700), default="")


def _maj_search_text(mapper, connection, produit: Product) -> None:
    produit.search_text = normaliser(
        f"{produit.nom} {produit.domaine} {produit.appellation} {produit.region} "
        f"{produit.millesime or ''}"
    )


event.listen(Product, "before_insert", _maj_search_text)
event.listen(Product, "before_update", _maj_search_text)
