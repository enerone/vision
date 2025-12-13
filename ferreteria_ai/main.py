import base64
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import List

import numpy as np
import ollama
import pandas as pd
from fastapi import FastAPI, Request, UploadFile, File, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import models
from .database import SessionLocal, engine, create_db_and_tables

# --- Configuración ---
OLLAMA_MODEL = "qwen3-vl"
UPLOADS_DIR = Path("ferreteria_ai/static/uploads")

# Categorías disponibles
CATEGORIES = [
    "Herramientas",
    "Herramientas Eléctricas",
    "Fijaciones",
    "Abrasivos",
    "Electricidad",
    "Plomería",
    "Pinturería",
    "Seguridad",
    "Otros"
]

# --- Inicialización de la App ---
app = FastAPI()

# Crear base de datos y tablas al iniciar
@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Crear el directorio para las imágenes de productos si no existe
    UPLOADS_DIR.mkdir(exist_ok=True)

# Montar directorios estáticos
app.mount("/static", StaticFiles(directory="ferreteria_ai/static"), name="static")
templates = Jinja2Templates(directory="ferreteria_ai/templates")

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
    return templates.TemplateResponse("add_product.html", {"request": request, "categories": CATEGORIES})


@app.get("/products", response_class=HTMLResponse)
async def list_products(request: Request, db: Session = Depends(get_db)):
    """
    Muestra una lista de todos los productos en el inventario.
    """
    products_db = db.query(models.Product).order_by(models.Product.name).all()

    # Convertir los productos a diccionarios para que sean serializables a JSON
    products_list = []
    for p in products_db:
        products_list.append({
            'id': p.id,
            'name': p.name,
            'code': p.code,
            'category': p.category,
            'description': p.description,
            'stock': p.stock,
            'price': float(p.price),
            'image_path': p.image_path
        })

    return templates.TemplateResponse("product_list.html", {
        "request": request,
        "products": products_list
    })


@app.post("/products")
async def create_product(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    category: str = Form("Otros"),
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

    # Guardar la imagen en el servidor con un nombre único
    file_extension = os.path.splitext(image.filename)[1]  # Obtener la extensión (.jpg, .png, etc.)
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    image_path = UPLOADS_DIR / unique_filename
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

    # Crear la ruta relativa para servir la imagen (sin el prefijo ferreteria_ai/)
    relative_image_path = f"static/uploads/{unique_filename}"

    # Crear la nueva instancia del producto
    new_product = models.Product(
        name=name,
        code=code,
        category=category,
        description=description,
        stock=stock,
        price=price,
        image_path=relative_image_path,
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
    return templates.TemplateResponse("edit_product.html", {"request": request, "product": product, "categories": CATEGORIES})


@app.post("/products/{product_id}/edit")
async def update_product(
    product_id: int,
    name: str = Form(...),
    code: str = Form(...),
    category: str = Form("Otros"),
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
    product.category = category
    product.description = description
    product.stock = stock
    product.price = price

    # Si se subió una nueva imagen, procesarla
    if image and image.filename:
        # Borrar la imagen antigua si existe (construir ruta completa)
        old_image_full_path = Path("ferreteria_ai") / product.image_path
        if old_image_full_path.exists():
            os.remove(old_image_full_path)

        # Guardar la nueva imagen con un nombre único
        file_extension = os.path.splitext(image.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        image_path = UPLOADS_DIR / unique_filename
        with image_path.open("wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # Guardar ruta relativa
        product.image_path = f"static/uploads/{unique_filename}"

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


@app.post("/products/import")
async def import_products_from_excel(
    excel_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Importa productos desde un archivo Excel.
    El archivo debe tener las columnas: name, code, category, description, stock, price
    """
    try:
        # Validar el archivo
        if not excel_file or not excel_file.filename:
            raise HTTPException(status_code=400, detail="No se recibió ningún archivo")

        print(f"Archivo recibido: {excel_file.filename}")
        print(f"Content-Type: {excel_file.content_type}")

        # Leer el archivo Excel
        contents = await excel_file.read()
        print(f"Tamaño del archivo: {len(contents)} bytes")

        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="El archivo está vacío")

        # Usar BytesIO para evitar la advertencia de pandas
        from io import BytesIO
        excel_buffer = BytesIO(contents)

        # Intentar leer el Excel
        # Primero intentar leer sin especificar header para detectar la estructura
        df_preview = pd.read_excel(excel_buffer, header=None, nrows=10)

        print("Primeras 10 filas del Excel:")
        for idx, row in df_preview.iterrows():
            print(f"  Fila {idx}: {list(row[:5])}")  # Mostrar primeras 5 columnas

        # Buscar la fila que contiene los encabezados reales
        # Debe tener al menos 3 de las columnas clave
        header_row = None
        for idx, row in df_preview.iterrows():
            row_values = [str(cell).lower() for cell in row if pd.notna(cell)]

            # Contar cuántas columnas clave contiene esta fila
            key_columns_found = 0
            keywords = ['sku', 'producto', 'stock', 'precio', 'categoria', 'categoría']

            for cell in row_values:
                for keyword in keywords:
                    if keyword in cell:
                        key_columns_found += 1
                        break

            # Si encontramos al menos 3 columnas clave, es probable que sea el header
            if key_columns_found >= 3:
                header_row = idx
                print(f"Fila de encabezados detectada en índice {idx} con {key_columns_found} columnas clave")
                break

        # Si encontramos los encabezados, leer el Excel desde esa fila
        # Reiniciar el buffer
        excel_buffer.seek(0)

        if header_row is not None:
            print(f"Encabezados encontrados en la fila {header_row}")
            df = pd.read_excel(excel_buffer, header=header_row)
        else:
            # Si no encontramos encabezados, intentar leer normalmente
            df = pd.read_excel(excel_buffer)

        # Eliminar filas completamente vacías
        df = df.dropna(how='all')

        print(f"Filas leídas: {len(df)}")
        print(f"Columnas encontradas: {list(df.columns)}")

        # Mapeo flexible de columnas
        # Intentar detectar automáticamente las columnas basándose en nombres comunes
        column_mapping = {}

        # Mapeo para 'name' (nombre del producto)
        name_candidates = ['name', 'nombre', 'producto', 'descripcion', 'description', 'item']
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in name_candidates or 'producto' in col_lower or 'nombre' in col_lower:
                column_mapping['name'] = col
                break

        # Mapeo para 'code' (código/SKU)
        code_candidates = ['code', 'codigo', 'sku', 'id', 'id/sku']
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in code_candidates or 'sku' in col_lower or 'codigo' in col_lower or 'código' in col_lower:
                column_mapping['code'] = col
                break

        # Mapeo para 'category' (categoría)
        category_candidates = ['category', 'categoria', 'categoría', 'tipo', 'type']
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in category_candidates or 'categor' in col_lower:
                column_mapping['category'] = col
                break

        # Mapeo para 'stock' (stock/cantidad)
        stock_candidates = ['stock', 'cantidad', 'existencia', 'inventory']
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in stock_candidates or 'stock' in col_lower or 'cantidad' in col_lower:
                column_mapping['stock'] = col
                break

        # Mapeo para 'price' (precio)
        price_candidates = ['price', 'precio', 'precio unitario', 'precio_unitario', 'valor']
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in price_candidates or 'precio' in col_lower:
                # Preferir precio sin IVA
                if 'unitario' in col_lower or ('precio' in col_lower and 'iva' not in col_lower):
                    column_mapping['price'] = col
                    break

        # Si no encontramos precio unitario, buscar cualquier columna con precio
        if 'price' not in column_mapping:
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if 'precio' in col_lower:
                    column_mapping['price'] = col
                    break

        print(f"Mapeo de columnas detectado: {column_mapping}")

        # Validar que encontramos todas las columnas necesarias
        required_fields = ['name', 'code', 'stock', 'price']
        missing_fields = [field for field in required_fields if field not in column_mapping]

        if missing_fields:
            available_cols = ', '.join(list(df.columns))
            raise HTTPException(
                status_code=400,
                detail=f"No se pudieron detectar las columnas: {', '.join(missing_fields)}. Columnas disponibles: {available_cols}"
            )

        # Renombrar las columnas del DataFrame
        rename_dict = {v: k for k, v in column_mapping.items()}
        df = df.rename(columns=rename_dict)

        print(f"DataFrame renombrado con columnas: {list(df.columns)}")

        # Estadísticas de importación
        imported = 0
        skipped = 0
        errors = []

        for index, row in df.iterrows():
            try:
                # Verificar si el producto ya existe
                code_value = str(row['code']).strip() if pd.notna(row['code']) else None
                if not code_value:
                    skipped += 1
                    errors.append(f"Fila {index + 2}: Código/SKU vacío")
                    continue

                existing = db.query(models.Product).filter(
                    models.Product.code == code_value
                ).first()

                if existing:
                    skipped += 1
                    errors.append(f"Fila {index + 2}: Código '{code_value}' ya existe")
                    continue

                # Obtener nombre del producto
                name_value = str(row['name']).strip() if pd.notna(row['name']) else None
                if not name_value:
                    skipped += 1
                    errors.append(f"Fila {index + 2}: Nombre de producto vacío")
                    continue

                # Obtener descripción (opcional)
                description = str(row.get('description', '')) if pd.notna(row.get('description')) else ''

                # Para productos importados sin imagen, usar una imagen placeholder
                # El usuario deberá agregar la imagen manualmente después
                placeholder_image = "static/uploads/placeholder.svg"

                # Generar embedding placeholder (se actualizará cuando agreguen la imagen)
                # Por ahora usamos un vector vacío o un embedding de texto del nombre
                try:
                    embedding_response = ollama.embeddings(
                        model='nomic-embed-text',
                        prompt=f"{name_value} - {description}"
                    )
                    embedding = embedding_response.get("embedding", [0] * 768)
                except:
                    # Si falla, usar vector de ceros
                    embedding = [0] * 768

                # Obtener categoría (con validación)
                # Si la columna 'category' existe en el mapping, usarla; si no, usar 'Otros'
                if 'category' in row and pd.notna(row['category']):
                    category = str(row['category']).strip()
                    # Mapear categorías comunes
                    category_lower = category.lower()
                    if 'herrami' in category_lower and 'elect' in category_lower:
                        category = 'Herramientas Eléctricas'
                    elif 'herrami' in category_lower:
                        category = 'Herramientas'
                    elif 'fijac' in category_lower or 'tornill' in category_lower:
                        category = 'Fijaciones'
                    elif 'abrasiv' in category_lower or 'lija' in category_lower:
                        category = 'Abrasivos'
                    elif 'electric' in category_lower or 'cable' in category_lower:
                        category = 'Electricidad'
                    elif 'plomer' in category_lower or 'cañ' in category_lower or 'tuber' in category_lower:
                        category = 'Plomería'
                    elif 'pintur' in category_lower or 'pintura' in category_lower:
                        category = 'Pinturería'
                    elif 'segur' in category_lower:
                        category = 'Seguridad'

                    # Validar que esté en la lista
                    if category not in CATEGORIES:
                        category = 'Otros'
                else:
                    category = 'Otros'

                # Obtener y validar stock
                stock_value = 0
                if pd.notna(row['stock']):
                    try:
                        stock_value = int(float(row['stock']))  # Convertir a float primero por si tiene decimales
                    except:
                        stock_value = 0

                # Obtener y validar precio
                price_value = 0.0
                if pd.notna(row['price']):
                    try:
                        # Limpiar el precio (quitar símbolos de moneda, comas, etc.)
                        price_str = str(row['price']).replace('$', '').replace(',', '').strip()
                        price_value = float(price_str)
                    except:
                        price_value = 0.0

                # Crear el producto
                new_product = models.Product(
                    name=name_value,
                    code=code_value,
                    category=category,
                    description=description,
                    stock=stock_value,
                    price=price_value,
                    image_path=placeholder_image,
                    embedding=embedding
                )

                db.add(new_product)
                imported += 1

            except Exception as e:
                errors.append(f"Fila {index + 2}: {str(e)}")
                skipped += 1

        # Guardar cambios
        db.commit()

        return JSONResponse(content={
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10]  # Mostrar solo los primeros 10 errores
        })

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error al procesar el archivo: {str(e)}"}
        )


@app.get("/products/template")
async def download_template():
    """
    Descarga una plantilla de Excel para importar productos
    Compatible con formato de ferretería estándar
    """
    # Crear un DataFrame de ejemplo con nombres de columnas en español
    df = pd.DataFrame({
        'ID/SKU': ['TOR-001', 'DES-001', 'CAB-001'],
        'Producto': ['Tornillo M8', 'Destornillador Phillips', 'Cable eléctrico 2.5mm'],
        'Categoría': ['Fijaciones', 'Herramientas', 'Electricidad'],
        'Stock': [100, 50, 200],
        'Precio unitario ($)': [0.50, 15.99, 2.50]
    })

    # Guardar temporalmente
    temp_path = Path("/tmp/plantilla_productos.xlsx")
    df.to_excel(temp_path, index=False)

    # Leer y devolver
    from fastapi.responses import FileResponse
    return FileResponse(
        path=temp_path,
        filename="plantilla_productos.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

