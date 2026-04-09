import sqlite3
from pathlib import Path

import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from datetime import date, datetime, timedelta, timezone
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends

# Change execution policy
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# .\.venv\Scripts\Activate.ps1

app = FastAPI()
security = HTTPBearer()

DATABASE_PATH = Path(__file__).with_name("users.db")

password_hash = PasswordHash((
    Argon2Hasher(),
))

# JWT credentials
SECRET_KEY = "f62aa222ef5412d5d733bf26fa5d86b605dd76d79c050878ba0044833c48e35b"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRY_MINUTES = 2400

# Helper to extract raw token


def get_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    return credentials.credentials


def get_current_user(token: str = Depends(get_token)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials.",
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        user_id = int(user_id)

    except (InvalidTokenError, ValueError):
        raise credentials_exception

    with get_connection() as connection:
        current_user = connection.execute(
            """
            SELECT id, name, email, role
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    if not current_user:
        raise credentials_exception

    return current_user


class AccessToken(BaseModel):
    access_token: str
    token_type: str


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + \
            timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Gain connection to the database


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

# Set-up the database


def initialize_database():
    with get_connection() as connection:
        # Creates user table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL)
""")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS assignments(
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                due_date TEXT,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL)
                       """)
        connection.commit()


initialize_database()

# Requests base model


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


class AssignmentCreateRequest(BaseModel):
    title: str
    description: str
    due_date: date


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
                status_code=401, detail="Invalid credentials!"
            )

        valid_password = password_hash.verify(
            user_password, existing_user["password_hash"])

        if not valid_password:
            raise HTTPException(
                status_code=401, detail="Invalid credentials!"
            )

        access_token = create_access_token(
            data={
                "sub": str(existing_user["id"]),
                "role": existing_user["role"],
            }
        )

        return {
            "message": f"Dear {existing_user['name']}, welcome to the studying assistant as a {existing_user['role']}!",
            "user": {
                "id": existing_user["id"],
                "name": existing_user["name"],
                "email": existing_user["email"],
                "role": existing_user["role"]
            },
            "access_token": access_token,
            "token_type": "bearer"

        }


@app.post("/assignments")
def assignments(payload: AssignmentCreateRequest, current_user=Depends(get_current_user)):
    if current_user["role"] != "teacher":
        raise HTTPException(
            status_code=403,
            detail="Only teachers can create assignments."
        )
    title = payload.title.strip()
    description = payload.description.strip()
    due_date = payload.due_date.isoformat()
    created_by = current_user["id"]
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT INTO assignments(title, description, due_date, created_by, created_at) VALUES (?, ?, ?, ?, ?)
""", (title, description, due_date, created_by, created_at),)
        connection.commit()

    return {
        "message": "Assignment created successfully.",
        "assignment": {
            "id": cursor.lastrowid,
            "title": title,
            "description": description,
            "due_date": due_date,
            "created_by": created_by,
            "created_at": created_at,
        },
    }
