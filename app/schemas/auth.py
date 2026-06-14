from pydantic import BaseModel, EmailStr

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class CurrentUser(ORMModel):
    id: str
    name: str
    email: EmailStr
    role: str
    library_id: str
    branch_id: str | None = None
