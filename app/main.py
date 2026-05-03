from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import get_session, init_db
from app.models import Product

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Tienda — Dashboard", lifespan=lifespan)
SessionDep = Annotated[Session, Depends(get_session)]


def _parse_precio(value: str) -> Decimal:
    try:
        return Decimal(value.replace(",", ".").strip())
    except (InvalidOperation, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Precio no válido",
        )


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: SessionDep):
    products = session.exec(select(Product)).all()
    total_productos = len(products)
    stock_bajo = sum(1 for p in products if p.stock < 5)
    valor_inventario = sum((p.precio * p.stock) for p in products)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Dashboard",
            "total_productos": total_productos,
            "stock_bajo": stock_bajo,
            "valor_inventario": valor_inventario,
            "productos_recientes": sorted(products, key=lambda p: p.id or 0, reverse=True)[:8],
        },
    )


@app.get("/productos", response_class=HTMLResponse)
def listar_productos(request: Request, session: SessionDep):
    productos = session.exec(select(Product).order_by(Product.nombre)).all()
    return templates.TemplateResponse(
        request,
        "productos_lista.html",
        {"title": "Productos", "productos": productos},
    )


@app.get("/productos/nuevo", response_class=HTMLResponse)
def form_nuevo_producto(request: Request):
    return templates.TemplateResponse(
        request,
        "producto_form.html",
        {"title": "Nuevo producto", "producto": None, "action": "/productos", "method": "post"},
    )


@app.post("/productos", response_class=HTMLResponse)
def crear_producto(
    request: Request,
    session: SessionDep,
    nombre: Annotated[str, Form()],
    precio: Annotated[str, Form()],
    stock: Annotated[int, Form()],
    descripcion: Annotated[str, Form()] = "",
    categoria: Annotated[str, Form()] = "General",
):
    producto = Product(
        nombre=nombre.strip(),
        descripcion=descripcion.strip(),
        precio=_parse_precio(precio),
        stock=max(0, stock),
        categoria=categoria.strip() or "General",
    )
    session.add(producto)
    session.commit()
    session.refresh(producto)
    return RedirectResponse(url="/productos", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/productos/{producto_id}/editar", response_class=HTMLResponse)
def form_editar_producto(request: Request, producto_id: int, session: SessionDep):
    producto = session.get(Product, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return templates.TemplateResponse(
        request,
        "producto_form.html",
        {
            "title": "Editar producto",
            "producto": producto,
            "action": f"/productos/{producto_id}",
            "method": "post",
        },
    )


@app.post("/productos/{producto_id}", response_class=HTMLResponse)
def actualizar_producto(
    request: Request,
    producto_id: int,
    session: SessionDep,
    nombre: Annotated[str, Form()],
    precio: Annotated[str, Form()],
    stock: Annotated[int, Form()],
    descripcion: Annotated[str, Form()] = "",
    categoria: Annotated[str, Form()] = "General",
):
    producto = session.get(Product, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    producto.nombre = nombre.strip()
    producto.descripcion = descripcion.strip()
    producto.precio = _parse_precio(precio)
    producto.stock = max(0, stock)
    producto.categoria = categoria.strip() or "General"
    session.add(producto)
    session.commit()
    return RedirectResponse(url="/productos", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/productos/{producto_id}/eliminar", response_class=HTMLResponse)
def eliminar_producto(producto_id: int, session: SessionDep):
    producto = session.get(Product, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    session.delete(producto)
    session.commit()
    return RedirectResponse(url="/productos", status_code=status.HTTP_303_SEE_OTHER)
