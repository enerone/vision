from sqlalchemy import Column, Integer, String, Float, Text, JSON
from .database import Base

class Product(Base):
    """
    Modelo de la tabla de productos para la base de datos.
    """
    __tablename__ = "products"

    # --- Columnas de la tabla ---

    # Identificador único para cada producto
    id = Column(Integer, primary_key=True, index=True)

    # Nombre del producto (ej: "Tornillo de cabeza hexagonal")
    name = Column(String, index=True, nullable=False)

    # Código de producto o SKU. Debe ser único.
    code = Column(String, unique=True, index=True, nullable=False)

    # Categoría del producto
    category = Column(String, index=True, nullable=False, default="Otros")

    # Descripción más detallada del producto
    description = Column(Text, nullable=True)

    # Cantidad en inventario
    stock = Column(Integer, default=0)

    # Precio del producto
    price = Column(Float, default=0.0)

    # Ruta al archivo de imagen guardado localmente
    image_path = Column(String, nullable=False)

    # El "ADN" visual (vector embedding) guardado como un objeto JSON.
    # Usamos JSON porque es un tipo de dato flexible soportado por SQLite.
    embedding = Column(JSON, nullable=False)
