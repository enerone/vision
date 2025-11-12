from ferreteria_ai.database import create_db_and_tables

if __name__ == "__main__":
    print("Attempting to create database and tables...")
    try:
        create_db_and_tables()
        print("Database and tables created successfully (or already exist).")
    except Exception as e:
        print(f"Error creating database and tables: {e}")
