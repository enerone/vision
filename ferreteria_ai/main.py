import base64
import json
import os
import shutil
from pathlib import Path

import numpy as np
import ollama
from fastapi import FastAPI, Request, UploadFile, File, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import models
from database import SessionLocal, engine, create_db_and_tables

# --- Configuración ---
OLLAMA_MODEL = "qwen3-vl"
UPLOADS_DIR = Path("static/uploads")

# --- Inicialización de la App ---
app = FastAPI()

# Crear base de datos y tablas al iniciar
@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Crear el directorio para las imágenes de productos si no existe
    UPLOADS_DIR.mkdir(exist_ok=True)

# Montar directorios estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Dependencias ---
def get_db():
    """
    Crea una sesión de base de datos por cada petición.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Sirve la página principal de identificación."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/products/new", response_class=HTMLResponse)
async def show_add_product_form(request: Request):
    """Muestra el formulario para añadir un nuevo producto."""
    return templates.TemplateResponse("add_product.html", {"request": request})


@app.get("/products", response_class=HTMLResponse)
async def list_products(request: Request, db: Session = Depends(get_db)):
    """
    Muestra una lista de todos los productos en el inventario.
    """
    products = db.query(models.Product).order_by(models.Product.name).all()
    return templates.TemplateResponse("product_list.html", {"request": request, "products": products})


@app.post("/products")
async def create_product(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    description: str = Form(""),
    stock: int = Form(0),
    price: float = Form(0.0),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo producto en la base de datos.
    """
    # Verificar si el producto ya existe por su código
    existing_product = db.query(models.Product).filter(models.Product.code == code).first()
    if existing_product:
        # Aquí podríamos devolver un error a la plantilla, pero por ahora lo dejamos simple
        raise HTTPException(status_code=400, detail=f"El código de producto '{code}' ya existe.")

    # Guardar la imagen en el servidor
    image_path = UPLOADS_DIR / image.filename
    with image_path.open("wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # --- Proceso de Embedding en 2 Pasos ---
    try:
        image_bytes = image_path.read_bytes()

        # 1. Generar descripción de la imagen con el modelo de visión (qwen3-vl)
        vision_prompt = "Describe este objeto de ferretería en una frase corta y técnica. Sé muy específico. Por ejemplo: 'Tornillo de cabeza hexagonal M8x25mm' o 'Destornillador de estrella PH2'."
        description_response = ollama.generate(
            model=OLLAMA_MODEL, # Sigue siendo qwen3-vl
            prompt=vision_prompt,
            images=[image_bytes]
        )
        image_description = description_response.get('response', '').strip()
        if not image_description:
            raise HTTPException(status_code=500, detail="El modelo de visión no pudo describir la imagen.")

        # 2. Generar embedding del texto de la descripción con el modelo de embedding
        embedding_response = ollama.embeddings(
            model='nomic-embed-text',
            prompt=image_description
        )
        embedding = embedding_response.get("embedding")
        if not embedding:
            raise HTTPException(status_code=500, detail="El modelo 'nomic-embed-text' no devolvió un embedding.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante el proceso de embedding: {e}")

    # Crear la nueva instancia del producto
    new_product = models.Product(
        name=name,
        code=code,
        description=description,
        stock=stock,
        price=price,
        image_path=str(image_path),
        embedding=embedding
    )

    # Añadir a la base de datos
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    # Redirigir a la misma página para poder añadir otro producto
    return RedirectResponse(url="/products/new", status_code=303)


@app.post("/products/{product_id}/delete")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """
    Elimina un producto de la base de datos y su imagen asociada.
    """
    # Buscar el producto en la base de datos
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    # Eliminar el archivo de imagen del servidor
    try:
        if os.path.exists(product.image_path):
            os.remove(product.image_path)
    except Exception as e:
        # Si falla la eliminación del archivo, al menos lo notificamos, pero continuamos
        print(f"Advertencia: No se pudo eliminar el archivo de imagen {product.image_path}. Error: {e}")

    # Eliminar el producto de la base de datos
    db.delete(product)
    db.commit()

    # Redirigir de vuelta a la lista de productos
    return RedirectResponse(url="/products", status_code=303)


@app.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def show_edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Muestra el formulario para editar un producto existente.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    return templates.TemplateResponse("edit_product.html", {"request": request, "product": product})


@app.post("/products/{product_id}/edit")
async def update_product(
    product_id: int,
    name: str = Form(...),
    code: str = Form(...),
    description: str = Form(""),
    stock: int = Form(0),
    price: float = Form(0.0),
    image: UploadFile = File(None), # La imagen es opcional
    db: Session = Depends(get_db)
):
    """
    Actualiza un producto existente en la base de datos.
    """
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    # Actualizar campos de texto y numéricos
    product.name = name
    product.code = code
    product.description = description
    product.stock = stock
    product.price = price

    # Si se subió una nueva imagen, procesarla
    if image and image.filename:
        # Borrar la imagen antigua si existe
        if os.path.exists(product.image_path):
            os.remove(product.image_path)

        # Guardar la nueva imagen
        image_path = UPLOADS_DIR / image.filename
        with image_path.open("wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        
        product.image_path = str(image_path)

        # Recalcular el embedding, ya que la imagen ha cambiado
        try:
            image_bytes = image_path.read_bytes()
            vision_prompt = "Describe este objeto de ferretería en una frase corta y técnica."
            description_response = ollama.generate(model=OLLAMA_MODEL, prompt=vision_prompt, images=[image_bytes])
            image_description = description_response.get('response', '').strip()
            
            embedding_response = ollama.embeddings(model='nomic-embed-text', prompt=image_description)
            embedding = embedding_response.get("embedding")
            
            if not embedding:
                raise HTTPException(status_code=500, detail="No se pudo recalcular el embedding para la nueva imagen.")
            
            product.embedding = embedding
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error durante el proceso de embedding: {e}")

    db.commit()
    db.refresh(product)

    return RedirectResponse(url="/products", status_code=303)


@app.post("/api/identify")
async def identify_piece(
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Recibe una imagen, la compara con el inventario y devuelve una lista
    de posibles coincidencias que superen el umbral de confianza.
    """
    try:
        image_bytes = await image.read()

        # --- Proceso de Embedding en 2 Pasos para la imagen en vivo ---
        vision_prompt = "Describe este objeto de ferretería en una frase corta y técnica. Sé muy específico."
        description_response = ollama.generate(model=OLLAMA_MODEL, prompt=vision_prompt, images=[image_bytes])
        image_description = description_response.get('response', '').strip()
        if not image_description:
            return JSONResponse(status_code=500, content={"error": "El modelo de visión no pudo describir la imagen capturada."})

        embedding_response = ollama.embeddings(model='nomic-embed-text', prompt=image_description)
        live_embedding = embedding_response.get("embedding")
        if not live_embedding:
            return JSONResponse(status_code=500, content={"error": "El modelo de embedding no devolvió un vector."})

        # --- Búsqueda y Comparación ---
        products = db.query(models.Product).all()
        if not products:
            return JSONResponse(status_code=404, content={"identification": "No hay productos en el inventario para comparar."})

        inventory_embeddings = np.array([p.embedding for p in products])
        live_embedding_np = np.array(live_embedding)

        norm_live_value = np.linalg.norm(live_embedding_np)
        if norm_live_value == 0:
            return JSONResponse(status_code=500, content={"error": "No se pudo calcular la similitud por un embedding inválido (norma de embedding en vivo es cero)."})
        
        # Calcular similitudes
        dot_products = np.dot(inventory_embeddings, live_embedding_np)
        norm_inventory = np.linalg.norm(inventory_embeddings, axis=1)
        
        # Evitar división por cero si alguna norma del inventario es cero
        if np.any(norm_inventory == 0):
            return JSONResponse(status_code=500, content={"error": "No se pudo calcular la similitud por un embedding inválido (alguna norma de embedding del inventario es cero)."})

        similarities = dot_products / (norm_live_value * norm_inventory)

        # Encontrar todos los candidatos que superen el umbral
        CONFIDENCE_THRESHOLD = 0.65
        candidate_indices = np.where(similarities > CONFIDENCE_THRESHOLD)[0]

        if len(candidate_indices) == 0:
            best_score = np.max(similarities) if len(similarities) > 0 else 0
            return JSONResponse(
                status_code=404,
                content={"identification": f"No se encontró un producto similar (mejor puntuación: {best_score:.2f})."}
            )

        # Crear una lista de candidatos con sus datos y puntuación
        candidates = []
        for i in candidate_indices:
            product = products[i]
            candidates.append({
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "code": product.code,
                    "description": product.description,
                    "stock": product.stock,
                    "price": product.price,
                    "image_path": f"/{product.image_path}"
                },
                "similarity_score": float(similarities[i])
            })
        
        # Ordenar candidatos por puntuación descendente
        sorted_candidates = sorted(candidates, key=lambda x: x['similarity_score'], reverse=True)

        return JSONResponse(content={"matches": sorted_candidates})

    except Exception as e:
        print(f"Error inesperado en la identificación: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Ocurrió un error inesperado en el servidor durante la identificación."}
        )

