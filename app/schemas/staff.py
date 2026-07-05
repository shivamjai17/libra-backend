from pydantic import BaseModel, EmailStr

from app.models.enums import StaffRole
from app.schemas.common import ORMModel


class StaffCreate(BaseModel):
    name: str
    email: EmailStr
    role: StaffRole = StaffRole.FrontDesk
    password: str = "changeme123"
    branch_id: str | None = None


class StaffUpdate(BaseModel):
    name: str | None = None
    role: StaffRole | None = None
    active: bool | None = None
    branch_id: str | None = None


class StaffOut(ORMModel):
    id: str
    name: str
    email: EmailStr
    role: StaffRole
    active: bool
    branch_id: str | None = None
