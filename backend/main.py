import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

DATABASE_PATH = Path(__file__).with_name("users.db")

# Gain connection to the database


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

# Set-up the database


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE
                       )
""")
        connection.commit()


initialize_database()


class GreetRequest(BaseModel):
    name: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    email: str


@app.get("/")
def hello():
    return {"Hello": "World!"}


@app.get("/users")
def users_page():
    users = []

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT id, name, email FROM users ORDER BY id
                           """
                                  ).fetchall()
        connection.commit()

    for row in rows:
        users.append({
            "id": row["id"],
            "name": row["name"],
            "email": row["email"]
        })

    return users


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/greetings")
def greetings(payload: GreetRequest):
    return {"message": f"Good morning, {payload.name}"}

# Handles registration process


@app.post("/register")
def register(payload: RegisterRequest):
    normalized_name = payload.name.strip()
    normalized_email = payload.email.strip().lower()

    with get_connection() as connection:
        existing_user = connection.execute("""
            SELECT id FROM users WHERE email = ?""",
                                           (normalized_email,),

                                           ).fetchone()

        if existing_user:
            raise HTTPException(
                status_code=409, detail="Email already registered.")

        connection.execute("""
            INSERT INTO users(name, email) VALUES (?, ?)""",
                           (normalized_name, normalized_email),
                           )
        connection.commit()

    return {
        "message": f"{normalized_name} has successfully registered with {normalized_email}"
    }
