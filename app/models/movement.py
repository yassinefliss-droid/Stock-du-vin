from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TypeMouvement
from app.models.product import Product
from app.models.user import User


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    type: Mapped[TypeMouvement] = mapped_column(Enum(TypeMouvement, native_enum=False, length=20))
    # entree/sortie : > 0 ; ajustement : signé (écart d'inventaire).
    quantite: Mapped[int]
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    motif: Mapped[str] = mapped_column(String(255), default="")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    product: Mapped[Product] = relationship()
    user: Mapped[User | None] = relationship()

    @property
    def delta(self) -> int:
        return -self.quantite if self.type == TypeMouvement.sortie else self.quantite
