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
