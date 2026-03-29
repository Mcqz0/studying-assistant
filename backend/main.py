from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

registered_users = []


class GreetRequest(BaseModel):
    name: str


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    email: str


@app.get("/")
def hello():
    return {"Hello": "World!"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/greetings")
def greetings(payload: GreetRequest):
    return {"message": f"Good morning, {payload.name}"}


@app.post("/register")
def register(payload: RegisterRequest):

    normalized_email = payload.email.strip().lower()

    email_exists = any(
        user["email"].strip().lower() == normalized_email
        for user in registered_users
    )

    if email_exists:
        raise HTTPException(
            status_code=409, detail="Email already registered.")

    user_info = {
        "name": payload.name.strip(),
        "email": normalized_email
    }
    registered_users.append(user_info)
    return {"message": f"{payload.name} has successfully registered with {payload.email}"}
