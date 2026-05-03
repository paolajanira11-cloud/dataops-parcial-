"""Pruebas HTTP para CI (pytest + TestClient)."""

from urllib.parse import urlparse


def _general_id(client) -> int:
    r = client.get("/categorias")
    assert r.status_code == 200
    assert "General" in r.text
    from sqlmodel import Session, select

    from app.database import engine
    from app.models import Category

    with Session(engine) as session:
        row = session.exec(select(Category).where(Category.nombre == "General")).first()
        assert row is not None
        return int(row.id)


def test_dashboard_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Dashboard" in r.text


def test_categorias_list_contains_general(client):
    r = client.get("/categorias")
    assert r.status_code == 200
    assert "General" in r.text


def test_crear_categoria_y_redireccion(client):
    r = client.post(
        "/categorias",
        data={"nombre": "Bebidas", "descripcion": "Refrescos y agua"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    assert "categorias" in loc
    assert "toast=categoria_creada" in loc


def test_categoria_duplicada(client):
    client.post("/categorias", data={"nombre": "Unica", "descripcion": ""})
    r = client.post(
        "/categorias",
        data={"nombre": "Unica", "descripcion": "otra"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "categoria_duplicada" in (r.headers.get("location") or "")


def test_crear_producto_redireccion(client):
    gid = _general_id(client)
    r = client.post(
        "/productos",
        data={
            "nombre": "Agua 1L",
            "precio": "0,89",
            "stock": "12",
            "category_id": str(gid),
            "descripcion": "Mineral",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "toast=producto_creado" in (r.headers.get("location") or "")


def test_listado_productos_muestra_producto(client):
    gid = _general_id(client)
    client.post(
        "/productos",
        data={
            "nombre": "Teclado",
            "precio": "45.00",
            "stock": "3",
            "category_id": str(gid),
            "descripcion": "",
        },
    )
    r = client.get("/productos")
    assert r.status_code == 200
    assert "Teclado" in r.text


def test_editar_producto_not_found(client):
    r = client.get("/productos/99999/editar")
    assert r.status_code == 404


def test_eliminar_categoria_en_uso(client):
    gid = _general_id(client)
    client.post(
        "/productos",
        data={
            "nombre": "Solo",
            "precio": "1",
            "stock": "1",
            "category_id": str(gid),
            "descripcion": "",
        },
    )
    r = client.post(f"/categorias/{gid}/eliminar", follow_redirects=False)
    assert r.status_code == 303
    assert "categoria_en_uso" in (r.headers.get("location") or "")


def test_eliminar_categoria_vacia(client):
    client.post("/categorias", data={"nombre": "TempCat", "descripcion": ""})
    from sqlmodel import Session, select

    from app.database import engine
    from app.models import Category

    with Session(engine) as session:
        cat = session.exec(select(Category).where(Category.nombre == "TempCat")).first()
        cid = int(cat.id)
    r = client.post(f"/categorias/{cid}/eliminar", follow_redirects=False)
    assert r.status_code == 303
    loc = r.headers.get("location", "")
    assert urlparse(loc).path == "/categorias"
