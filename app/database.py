import os

from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


def _database_url() -> str:
    return os.environ.get("TIENDA_DATABASE_URL", "sqlite:///./tienda.db")


def _create_engine():
    url = _database_url()
    connect_args = {"check_same_thread": False}
    if ":memory:" in url:
        return create_engine(
            url,
            connect_args=connect_args,
            poolclass=StaticPool,
        )
    return create_engine(url, connect_args=connect_args)


engine = _create_engine()


def _migrate_legacy_product_categoria_column() -> None:
    """SQLite: tablas antiguas tenían `categoria` (texto); el modelo usa `category_id` (FK)."""
    url = str(engine.url)
    if ":memory:" in url:
        return
    insp = inspect(engine)
    if "product" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("product")}
    if "category_id" in cols:
        return
    if "categoria" not in cols:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO category (nombre, descripcion) "
                "SELECT 'General', '' WHERE NOT EXISTS (SELECT 1 FROM category WHERE nombre = 'General')"
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO category (nombre, descripcion)
                SELECT DISTINCT TRIM(p.categoria), ''
                FROM product p
                WHERE TRIM(COALESCE(p.categoria, '')) != ''
                AND NOT EXISTS (SELECT 1 FROM category c WHERE c.nombre = TRIM(p.categoria))
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE product_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    nombre VARCHAR(200) NOT NULL,
                    descripcion VARCHAR(2000) NOT NULL,
                    precio NUMERIC(12, 2) NOT NULL,
                    stock INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    FOREIGN KEY(category_id) REFERENCES category (id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO product_new (id, nombre, descripcion, precio, stock, category_id)
                SELECT
                    p.id,
                    p.nombre,
                    COALESCE(p.descripcion, ''),
                    p.precio,
                    COALESCE(p.stock, 0),
                    COALESCE(
                        c.id,
                        (SELECT id FROM category WHERE nombre = 'General' LIMIT 1)
                    )
                FROM product p
                LEFT JOIN category c ON c.nombre = TRIM(COALESCE(p.categoria, ''))
                """
            )
        )
        conn.execute(text("DROP TABLE product"))
        conn.execute(text("ALTER TABLE product_new RENAME TO product"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_product_nombre ON product (nombre)"))


def init_db() -> None:
    # Import models so metadata registers all tables
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate_legacy_product_categoria_column()


def get_session():
    with Session(engine) as session:
        yield session
