import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# Change execution policy
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass .\.venv\Scripts\Activate.ps1

app = FastAPI()

DATABASE_PATH = Path(__file__).with_name("users.db")

password_hash = PasswordHash((
    Argon2Hasher(),
))

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
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                       )
""")
        connection.commit()


initialize_database()


class GreetRequest(BaseModel):
    name: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    email: str
    password: str
    role: Literal["student", "teacher"]


class LoginRequest(BaseModel):
    email: str
    password: str


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
    hashed_password = password_hash.hash(payload.password)
    role = payload.role

    with get_connection() as connection:
        existing_user = connection.execute("""
            SELECT id FROM users WHERE email = ?""",
                                           (normalized_email,),

                                           ).fetchone()

        if existing_user:
            raise HTTPException(
                status_code=409, detail="Email already registered.")

        connection.execute("""
            INSERT INTO users(name, email, password_hash, role) VALUES (?, ?, ?, ?)""",
                           (normalized_name, normalized_email,
                            hashed_password, role),
                           )
        connection.commit()

    return {
        "message": f"{normalized_name}, who is a {role}, has successfully registered with {normalized_email}"
    }


@app.post("/login")
def login(payload: LoginRequest):
    normalized_email = payload.email.strip().lower()
    user_password = payload.password

    with get_connection() as connection:
        existing_user = connection.execute("""
            SELECT email, password_hash, id, role, name FROM users WHERE email = ?""",
                                           (normalized_email,),).fetchone()

        if not existing_user:
            raise HTTPException(
                status_code=401, detail="Email not found, please register."
            )

        valid_password = password_hash.verify(
            user_password, existing_user["password_hash"])

        if not valid_password:
            raise HTTPException(
                status_code=401, detail="Invalid password!"
            )

        return {
            "message": f"Dear {existing_user['name']}, welcome to the studying assistant as a {existing_user['role']}!",
            "user": {
                "id": existing_user["id"],
                "name": existing_user["name"],
                "email": existing_user["email"],
                "role": existing_user["role"]
            }
        }
