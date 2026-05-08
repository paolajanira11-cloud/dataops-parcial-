from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(index=True, max_length=100)
    descripcion: str = Field(default="", max_length=500)

    productos: List["Product"] = Relationship(back_populates="categoria")


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(index=True, max_length=200)
    descripcion: str = Field(default="", max_length=2000)
    precio: Decimal = Field(default=Decimal("0"), max_digits=12, decimal_places=2)
    stock: int = Field(default=0, ge=0)
    category_id: int = Field(foreign_key="category.id")

    categoria: Category = Relationship(back_populates="productos")
    movimientos_kardex: List["Kardex"] = Relationship(back_populates="producto")


class Kardex(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    tipo_movimiento: str = Field(max_length=20)
    cantidad: int = Field(gt=0)
    stock_anterior: int = Field(ge=0)
    stock_resultante: int = Field(ge=0)
    observacion: str = Field(default="", max_length=500)
    fecha_movimiento: datetime = Field(default_factory=datetime.utcnow, index=True)

    producto: Product = Relationship(back_populates="movimientos_kardex")
