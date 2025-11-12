# Project Overview

This project is a web application for a hardware store, named "Ferreteria AI". It provides a web interface to manage the store's inventory and uses an AI-powered feature to identify products from images.

## Main Technologies

*   **Backend:** [FastAPI](https://fastapi.tiangolo.com/)
*   **Database:** [SQLAlchemy](https://www.sqlalchemy.org/) with a [SQLite](https://www.sqlite.org/index.html) database.
*   **Frontend:** [Jinja2](https://jinja.palletsprojects.com/en/3.1.x/) for templating.
*   **AI:** [Ollama](https://ollama.ai/) with the `qwen3-vl` model for image description and `nomic-embed-text` for generating embeddings.

## Architecture

The application is structured as a typical FastAPI project:

*   `main.py`: Contains the main application logic, including the API endpoints for CRUD operations and the AI-powered product identification.
*   `database.py`: Sets up the database connection and session management.
*   `models.py`: Defines the SQLAlchemy data models.
*   `templates/`: Contains the Jinja2 HTML templates for the user interface.
*   `static/`: Holds static files, including uploaded product images.

# Building and Running

To run this project, you need to have Python and the dependencies installed.

1.  **Install dependencies:**

    ```bash
    pip install -r ferreteria_ai/requirements.txt
    ```

2.  **Run the application:**

    ```bash
    uvicorn ferreteria_ai.main:app --reload
    ```

The application will be available at `http://127.0.0.1:8000`.

## Docker

The project also includes a `Dockerfile` and `docker-compose.yml`, which suggests it can be run in a containerized environment.

*   **Build and run with Docker Compose:**

    ```bash
    docker-compose up --build
    ```

# Development Conventions

*   **Database:** The application uses a SQLite database named `inventory.db`, which will be created in the root of the project directory.
*   **AI Model:** The application relies on an Ollama instance with the `qwen3-vl` and `nomic-embed-text` models available.
*   **Code Style:** The code follows standard Python conventions.
*   **API:** The main API endpoints are:
    *   `/`: The main page for product identification.
    *   `/products`: A list of all products in the inventory.
    *   `/products/new`: A form to add a new product.
    *   `/api/identify`: The endpoint that receives an image and returns a list of matching products.
