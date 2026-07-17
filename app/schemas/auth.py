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


class RegisterRequest(BaseModel):
    institute_name: str
    email: EmailStr
    phone: str | None = None
    branch: str = "Main Branch"
    owner_name: str
    address: str | None = None
    plan: str = "Starter"
    password: str
    # Optional data-URL/base64 logo captured during onboarding.
    logo_base64: str | None = None


class RegisterResponse(BaseModel):
    library_id: str
    status: str
    message: str


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminUser(ORMModel):
    id: str
    name: str
    email: EmailStr
