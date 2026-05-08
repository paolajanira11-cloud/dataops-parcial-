from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.database import engine, get_session, init_db
from app.models import Category, Kardex, Product

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _seed_default_category(session: Session) -> None:
    if session.exec(select(Category)).first() is None:
        session.add(Category(nombre="General", descripcion="Categoría por defecto"))
        session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        _seed_default_category(session)
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


def _categorias(session: Session) -> list[Category]:
    return session.exec(select(Category).order_by(Category.nombre)).all()


def _productos_con_categoria(session: Session) -> list[Product]:
    stmt = select(Product).options(selectinload(Product.categoria)).order_by(Product.nombre)
    return session.exec(stmt).all()


def _kardex_con_producto(session: Session) -> list[Kardex]:
    stmt = (
        select(Kardex)
        .options(selectinload(Kardex.producto))
        .order_by(Kardex.fecha_movimiento.desc(), Kardex.id.desc())
    )
    return session.exec(stmt).all()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: SessionDep):
    products = session.exec(select(Product).options(selectinload(Product.categoria))).all()
    categorias = session.exec(select(Category)).all()
    total_productos = len(products)
    stock_bajo = sum(1 for p in products if p.stock < 5)
    valor_inventario = sum((p.precio * p.stock) for p in products)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Dashboard",
            "total_productos": total_productos,
            "total_categorias": len(categorias),
            "stock_bajo": stock_bajo,
            "valor_inventario": valor_inventario,
            "productos_recientes": sorted(products, key=lambda p: p.id or 0, reverse=True)[:8],
        },
    )


@app.get("/productos", response_class=HTMLResponse)
def listar_productos(request: Request, session: SessionDep):
    productos = _productos_con_categoria(session)
    return templates.TemplateResponse(
        request,
        "productos_lista.html",
        {"title": "Productos", "productos": productos},
    )


@app.get("/productos/nuevo", response_class=HTMLResponse)
def form_nuevo_producto(request: Request, session: SessionDep):
    return templates.TemplateResponse(
        request,
        "producto_form.html",
        {
            "title": "Nuevo producto",
            "producto": None,
            "categorias": _categorias(session),
            "action": "/productos",
            "method": "post",
        },
    )


@app.post("/productos", response_class=HTMLResponse)
def crear_producto(
    session: SessionDep,
    nombre: Annotated[str, Form()],
    precio: Annotated[str, Form()],
    stock: Annotated[int, Form()],
    category_id: Annotated[int, Form()],
    descripcion: Annotated[str, Form()] = "",
):
    if session.get(Category, category_id) is None:
        raise HTTPException(status_code=400, detail="Categoría no válida")
    producto = Product(
        nombre=nombre.strip(),
        descripcion=descripcion.strip(),
        precio=_parse_precio(precio),
        stock=max(0, stock),
        category_id=category_id,
    )
    session.add(producto)
    session.commit()
    session.refresh(producto)
    return RedirectResponse(
        url="/productos?toast=producto_creado",
        status_code=status.HTTP_303_SEE_OTHER,
    )


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
            "categorias": _categorias(session),
            "action": f"/productos/{producto_id}",
            "method": "post",
        },
    )


@app.post("/productos/{producto_id}", response_class=HTMLResponse)
def actualizar_producto(
    producto_id: int,
    session: SessionDep,
    nombre: Annotated[str, Form()],
    precio: Annotated[str, Form()],
    stock: Annotated[int, Form()],
    category_id: Annotated[int, Form()],
    descripcion: Annotated[str, Form()] = "",
):
    if session.get(Category, category_id) is None:
        raise HTTPException(status_code=400, detail="Categoría no válida")
    producto = session.get(Product, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    producto.nombre = nombre.strip()
    producto.descripcion = descripcion.strip()
    producto.precio = _parse_precio(precio)
    producto.stock = max(0, stock)
    producto.category_id = category_id
    session.add(producto)
    session.commit()
    return RedirectResponse(
        url="/productos?toast=producto_actualizado",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/productos/{producto_id}/eliminar", response_class=HTMLResponse)
def eliminar_producto(producto_id: int, session: SessionDep):
    producto = session.get(Product, producto_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    session.delete(producto)
    session.commit()
    return RedirectResponse(
        url="/productos?toast=producto_eliminado",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --- Categorías CRUD ---


@app.get("/categorias", response_class=HTMLResponse)
def listar_categorias(request: Request, session: SessionDep):
    categorias = session.exec(select(Category).order_by(Category.nombre)).all()
    categorias_conteo: list[tuple[Category, int]] = []
    for c in categorias:
        n = len(session.exec(select(Product).where(Product.category_id == c.id)).all())
        categorias_conteo.append((c, n))
    return templates.TemplateResponse(
        request,
        "categorias_lista.html",
        {"title": "Categorías", "categorias_conteo": categorias_conteo},
    )


@app.get("/categorias/nueva", response_class=HTMLResponse)
def form_nueva_categoria(request: Request):
    return templates.TemplateResponse(
        request,
        "categoria_form.html",
        {"title": "Nueva categoría", "categoria": None, "action": "/categorias", "method": "post"},
    )


@app.post("/categorias", response_class=HTMLResponse)
def crear_categoria(
    session: SessionDep,
    nombre: Annotated[str, Form()],
    descripcion: Annotated[str, Form()] = "",
):
    nombre_limpio = nombre.strip()
    if not nombre_limpio:
        raise HTTPException(status_code=422, detail="El nombre es obligatorio")
    existe = session.exec(select(Category).where(Category.nombre == nombre_limpio)).first()
    if existe:
        return RedirectResponse(
            url="/categorias/nueva?toast=categoria_duplicada",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    session.add(Category(nombre=nombre_limpio, descripcion=descripcion.strip()))
    session.commit()
    return RedirectResponse(
        url="/categorias?toast=categoria_creada",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/categorias/{categoria_id}/editar", response_class=HTMLResponse)
def form_editar_categoria(request: Request, categoria_id: int, session: SessionDep):
    categoria = session.get(Category, categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return templates.TemplateResponse(
        request,
        "categoria_form.html",
        {
            "title": "Editar categoría",
            "categoria": categoria,
            "action": f"/categorias/{categoria_id}",
            "method": "post",
        },
    )


@app.post("/categorias/{categoria_id}", response_class=HTMLResponse)
def actualizar_categoria(
    categoria_id: int,
    session: SessionDep,
    nombre: Annotated[str, Form()],
    descripcion: Annotated[str, Form()] = "",
):
    categoria = session.get(Category, categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    nombre_limpio = nombre.strip()
    if not nombre_limpio:
        raise HTTPException(status_code=422, detail="El nombre es obligatorio")
    otra = session.exec(
        select(Category).where(Category.nombre == nombre_limpio, Category.id != categoria_id)
    ).first()
    if otra:
        return RedirectResponse(
            url=f"/categorias/{categoria_id}/editar?toast=categoria_duplicada",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    categoria.nombre = nombre_limpio
    categoria.descripcion = descripcion.strip()
    session.add(categoria)
    session.commit()
    return RedirectResponse(
        url="/categorias?toast=categoria_actualizada",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.post("/categorias/{categoria_id}/eliminar", response_class=HTMLResponse)
def eliminar_categoria(categoria_id: int, session: SessionDep):
    categoria = session.get(Category, categoria_id)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    if session.exec(select(Product).where(Product.category_id == categoria_id)).first():
        return RedirectResponse(
            url="/categorias?toast=categoria_en_uso",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    session.delete(categoria)
    session.commit()
    return RedirectResponse(
        url="/categorias?toast=categoria_eliminada",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --- Kardex ---


@app.get("/kardex", response_class=HTMLResponse)
def listar_kardex(request: Request, session: SessionDep):
    movimientos = _kardex_con_producto(session)
    return templates.TemplateResponse(
        request,
        "kardex_lista.html",
        {"title": "Kardex", "movimientos": movimientos},
    )


@app.get("/kardex/nuevo", response_class=HTMLResponse)
def form_nuevo_movimiento(request: Request, session: SessionDep):
    return templates.TemplateResponse(
        request,
        "kardex_form.html",
        {
            "title": "Nuevo movimiento de kardex",
            "productos": _productos_con_categoria(session),
        },
    )


@app.post("/kardex", response_class=HTMLResponse)
def crear_movimiento_kardex(
    session: SessionDep,
    product_id: Annotated[int, Form()],
    tipo_movimiento: Annotated[str, Form()],
    cantidad: Annotated[int, Form()],
    observacion: Annotated[str, Form()] = "",
):
    producto = session.get(Product, product_id)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if cantidad <= 0:
        raise HTTPException(status_code=422, detail="La cantidad debe ser mayor a cero")
    tipo = tipo_movimiento.strip().lower()
    if tipo not in {"entrada", "salida", "ajuste"}:
        raise HTTPException(status_code=422, detail="Tipo de movimiento no válido")

    stock_anterior = max(0, producto.stock)
    if tipo == "entrada":
        stock_resultante = stock_anterior + cantidad
    elif tipo == "salida":
        if cantidad > stock_anterior:
            return RedirectResponse(
                url="/kardex/nuevo?toast=kardex_stock_insuficiente",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        stock_resultante = stock_anterior - cantidad
    else:
        stock_resultante = cantidad

    movimiento = Kardex(
        product_id=producto.id,
        tipo_movimiento=tipo,
        cantidad=cantidad,
        stock_anterior=stock_anterior,
        stock_resultante=stock_resultante,
        observacion=observacion.strip(),
    )
    producto.stock = stock_resultante
    session.add(movimiento)
    session.add(producto)
    session.commit()
    return RedirectResponse(
        url="/kardex?toast=kardex_creado",
        status_code=status.HTTP_303_SEE_OTHER,
    )
