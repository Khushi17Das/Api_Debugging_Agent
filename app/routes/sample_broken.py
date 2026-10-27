import re
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status, Query
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/api/sample", tags=["Sample Playground Endpoints"])


class CreateUserModel(BaseModel):
    name: str
    email: str

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(pattern, v):
            raise ValueError("value is not a valid email address")
        return v


@router.get("/users/{user_id}")
def get_user(user_id: int):
    """Returns 404 if user_id does not exist."""
    if user_id != 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} does not exist in the database.",
        )
    return {"id": 1, "name": "Jane Developer", "role": "Backend Engineer"}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(user: CreateUserModel):
    """
    Creates a user. Returns 422 Unprocessable Entity if email is invalid format.
    Returns 201 Created if valid.
    """
    return {
        "status": "success",
        "message": "User successfully created.",
        "user": {"name": user.name, "email": user.email},
    }


@router.get("/divide")
def calculate_division(a: float = Query(..., description="Numerator"), b: float = Query(..., description="Denominator")):
    """
    Demonstrates Python runtime exception (ZeroDivisionError) returning 500 when b=0.
    Returns 200 when b != 0.
    """
    if b == 0:
        # Deliberately raise ZeroDivisionError to simulate unhandled exception
        raise ZeroDivisionError("division by zero")
    return {"numerator": a, "denominator": b, "result": a / b}


@router.get("/protected")
def get_protected_resource(authorization: Optional[str] = Header(None)):
    """
    Demonstrates 401 Unauthorized when Bearer token is missing or invalid.
    Returns 200 when Authorization header is 'Bearer valid_token_123'.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if authorization != "Bearer valid_token_123":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "status": "authorized",
        "message": "Access granted to secure telemetry dashboard.",
        "scope": ["read:telemetry", "write:metrics"],
    }


@router.post("/database-fail")
def simulate_database_failure():
    """Simulates a database failure scenario returning 500 with SQLAlchemy OperationalError."""
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file",
    )
