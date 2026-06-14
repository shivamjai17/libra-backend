from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import TenantContext, get_tenant
from app.core.database import get_db
from app.models.enums import StudentStatus
from app.models.student import Document, Note, Student
from app.schemas.common import Page
from app.schemas.student import (
    DocumentOut, NoteCreate, NoteOut, StudentCreate, StudentDetail, StudentOut, StudentUpdate,
)
from app.services import students as svc
from app.services.rules import derive_status

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=Page[StudentOut])
async def list_students(
    status: StudentStatus | None = None,
    batch_id: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: TenantContext = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Student).where(Student.branch_id == ctx.branch_id)
    if batch_id:
        stmt = stmt.where(Student.batch_id == batch_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(func.lower(Student.name).like(like), func.lower(Student.id).like(like), Student.phone.like(like))
        )
    rows = (await db.execute(stmt.order_by(Student.joined_date.desc()))).scalars().all()
    out = [svc.to_out(s) for s in rows]
    # Derived status is computed, so filter post-hoc.
    if status:
        out = [s for s in out if s.status == status]
    total = len(out)
    start = (page - 1) * page_size
    return Page(items=out[start : start + page_size], total=total, page=page, page_size=page_size)


@router.post("", response_model=StudentOut, status_code=201)
async def create_student(payload: StudentCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    student = await svc.onboard(db, ctx, payload)
    return svc.to_out(student)


@router.get("/{student_id}", response_model=StudentDetail)
async def get_student(student_id: str, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    student = await svc.load_one(db, student_id, with_subresources=True)
    if student is None or student.branch_id != ctx.branch_id:
        raise HTTPException(404, "Student not found")
    base = svc.to_out(student).model_dump()
    return StudentDetail(**base, documents=student.documents, notes=student.notes)


@router.patch("/{student_id}", response_model=StudentOut)
async def update_student(student_id: str, payload: StudentUpdate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    student = await svc.load_one(db, student_id)
    if student is None or student.branch_id != ctx.branch_id:
        raise HTTPException(404, "Student not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(student, k, v)
    await db.flush()
    return svc.to_out(await svc.load_one(db, student_id))


@router.post("/{student_id}/notes", response_model=NoteOut, status_code=201)
async def add_note(student_id: str, payload: NoteCreate, ctx: TenantContext = Depends(get_tenant), db: AsyncSession = Depends(get_db)):
    note = Note(student_id=student_id, body=payload.body, author=payload.author or ctx.user.name)
    db.add(note)
    await db.flush()
    return note
