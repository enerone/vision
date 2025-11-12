from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Definimos la URL de la base de datos.
# "sqlite:///./inventory.db" significa que usará un archivo llamado inventory.db
# en el mismo directorio.
SQLALCHEMY_DATABASE_URL = "sqlite:///./ferreteria_ai/inventory.db"

# 2. Creamos el "motor" de SQLAlchemy.
# El argumento connect_args es necesario solo para SQLite para permitir
# que se use en múltiples hilos, como lo hace FastAPI.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. Creamos una clase SessionLocal.
# Cada instancia de SessionLocal será una sesión de base de datos.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Creamos una clase Base.
# Nuestras clases de modelo de base de datos (la tabla Producto) heredarán de esta clase.
Base = declarative_base()

def create_db_and_tables():
    """
    Función para crear el archivo de la base de datos y todas las tablas.
    """
    Base.metadata.create_all(bind=engine)
