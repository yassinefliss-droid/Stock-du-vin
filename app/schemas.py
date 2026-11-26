from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import Couleur, Role, TypeMouvement


class ProduitBase(BaseModel):
    reference: str = Field(min_length=1, max_length=40)
    nom: str = Field(min_length=1, max_length=200)
    domaine: str
    appellation: str
    region: str
    millesime: int | None = Field(default=None, ge=1900, le=2100)
    couleur: Couleur
    format: str = "75cl"
    prix_achat: Decimal = Field(ge=0, decimal_places=2)
    prix_vente: Decimal = Field(ge=0, decimal_places=2)
    seuil_alerte: int = Field(default=6, ge=0)


class ProduitCreate(ProduitBase):
    pass


class ProduitUpdate(BaseModel):
    """Tous les champs sont optionnels (mise à jour partielle)."""

    nom: str | None = None
    domaine: str | None = None
    appellation: str | None = None
    region: str | None = None
    millesime: int | None = None
    couleur: Couleur | None = None
    format: str | None = None
    prix_achat: Decimal | None = Field(default=None, ge=0)
    prix_vente: Decimal | None = Field(default=None, ge=0)
    seuil_alerte: int | None = Field(default=None, ge=0)


class ProduitOut(ProduitBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProduitStockOut(ProduitOut):
    stock: int


class MouvementCreate(BaseModel):
    product_id: int
    type: TypeMouvement
    quantite: int = Field(description="> 0 pour entrée/sortie ; signé (+/-) pour un ajustement")
    date: datetime | None = Field(default=None, description="Par défaut : maintenant")
    motif: str = Field(default="", max_length=255)

    @model_validator(mode="after")
    def quantite_coherente(self):
        if self.type == TypeMouvement.ajustement:
            if self.quantite == 0:
                raise ValueError("Un ajustement doit avoir une quantité non nulle")
        elif self.quantite <= 0:
            raise ValueError("La quantité d'une entrée ou d'une sortie doit être positive")
        return self


class MouvementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    type: TypeMouvement
    quantite: int
    date: datetime
    motif: str
    user_id: int | None


class ValeurOut(BaseModel):
    references: int
    bouteilles: int
    valeur_achat: Decimal
    valeur_vente: Decimal


class StockProduitOut(BaseModel):
    product_id: int
    stock: int
    seuil_alerte: int
    sous_seuil: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Role.lecture_seule


class UserUpdate(BaseModel):
    role: Role | None = None
    actif: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: Role
    actif: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class ReponseAssistant(BaseModel):
    reponse: str
    mode: str
    outils: list[dict]


class PeriodeFiltre(BaseModel):
    debut: date | None = None
    fin: date | None = None
