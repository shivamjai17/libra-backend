"""Seed LibraDesk with the exact sample data from the design prototype.

Run:  python -m scripts.seed
Idempotent: clears existing rows for the demo library first.
"""
import asyncio
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.security import hash_password
from app.models.catalog import Batch, Hall, Plan, Seat
from app.models.enums import (
    AttendanceMethod, AttendanceStatus, NotificationChannel, NotificationType,
    PaymentMethod, PaymentStatus, PlanPeriod, SeatStatus, StaffRole,
)
from app.models.operations import AttendanceLog, Notification, Payment
from app.models.student import Student
from app.models.tenant import Branch, BranchSettings, Library, Staff

BRANCHES = [
    ("Anna Nagar", "Chennai · Main"),
    ("T. Nagar", "Chennai · South"),
    ("Velachery", "Chennai · IT Corridor"),
    ("Adyar", "Chennai · Coastal"),
    ("OMR", "Chennai · Tech Park"),
]

PLANS = [
    ("Premium", 18000, PlanPeriod.year, True),
    ("Standard", 9000, PlanPeriod.year, True),
    ("Day Pass", 150, PlanPeriod.day, False),
]

BATCHES = [
    ("Morning", "06:00", "11:00", "amber"),
    ("Afternoon", "12:00", "16:00", "blue"),
    ("Evening", "17:00", "21:00", "purple"),
]

HALLS = [
    ("Reading Hall A", "Ground Floor", 6, 12),
    ("Reading Hall B", "First Floor", 5, 10),
    ("Quiet Zone", "First Floor", 4, 8),
    ("Computer Lab", "Second Floor", 3, 8),
]

# id, name, phone, plan, seat-code, status-hint, due, joined, batch
STUDENTS = [
    ("2841", "Aarav Sharma", "+91 98765 43210", "Premium", "A-14", 0, "2026-01-12", "Morning"),
    ("2839", "Priya Iyer", "+91 98220 11234", "Standard", "B-7", 0, "2026-02-03", "Evening"),
    ("2835", "Vikram Singh", "+91 99001 22890", "Premium", None, 4500, "2025-03-18", "Afternoon"),
    ("2830", "Ananya Reddy", "+91 98401 55678", "Premium", "C-21", 0, "2025-11-22", "Morning"),
    ("2828", "Karthik Rao", "+91 90031 44556", "Standard", "B-19", 3200, "2026-04-09", "Evening"),
    ("2821", "Sneha Nair", "+91 99520 33421", "Standard", None, 2800, "2026-05-15", "Afternoon"),
    ("2817", "Ishaan Khan", "+91 98330 99001", "Premium", "A-2", 0, "2025-12-30", "Morning"),
    ("2810", "Diya Gupta", "+91 97411 22334", "Standard", "D-11", 0, "2026-02-11", "Evening"),
    ("2804", "Rohan Mehta", "+91 98905 67812", "Premium", None, 0, "2025-01-27", "Afternoon"),
    ("2799", "Meera Joshi", "+91 99300 45678", "Standard", "C-5", 0, "2026-03-06", "Morning"),
    ("2790", "Arjun Verma", "+91 98111 23456", "Premium", "D-3", 0, "2026-04-19", "Evening"),
    ("2785", "Kavya Menon", "+91 99887 65432", "Standard", "B-22", 1500, "2026-05-24", "Afternoon"),
]

PERIOD = {"Premium": PlanPeriod.year, "Standard": PlanPeriod.year, "Day Pass": PlanPeriod.day}
PERIOD_DAYS = {PlanPeriod.day: 1, PlanPeriod.year: 365}


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Reset demo library if present.
        existing = (await db.execute(select(Library).where(Library.name == "StudyHub Reading Center"))).scalar_one_or_none()
        if existing:
            await db.execute(delete(Library).where(Library.id == existing.id))
            await db.flush()

        lib = Library(
            name="StudyHub Reading Center", contact_phone="+91 44 4000 1234",
            gst_number="33ABCDE1234F1Z5", address="Anna Nagar, Chennai",
            timezone="Asia/Kolkata", accent_color="#0f7c5a",
        )
        db.add(lib)
        await db.flush()

        branches = []
        for name, area in BRANCHES:
            b = Branch(library_id=lib.id, name=name, area=area)
            db.add(b)
            await db.flush()
            db.add(BranchSettings(branch_id=b.id))
            branches.append(b)
        main = branches[0]

        # Owner login.
        db.add(Staff(
            library_id=lib.id, branch_id=main.id, name="Rahul Krishnan",
            email="owner@studyhub.in", hashed_password=hash_password("studyhub123"),
            role=StaffRole.Owner,
        ))

        # Catalog (scoped to main branch for the demo).
        plan_by_name = {}
        for name, price, period, seat in PLANS:
            p = Plan(library_id=lib.id, branch_id=main.id, name=name, price=price, period=period, seat_included=seat)
            db.add(p)
            await db.flush()
            plan_by_name[name] = p

        batch_by_name = {}
        for name, start, end, color in BATCHES:
            bt = Batch(library_id=lib.id, branch_id=main.id, name=name, start_time=start, end_time=end, color=color)
            db.add(bt)
            await db.flush()
            batch_by_name[name] = bt

        seat_by_code = {}
        for name, floor, rows, cols in HALLS:
            h = Hall(library_id=lib.id, branch_id=main.id, name=name, floor=floor, rows=rows, cols=cols)
            db.add(h)
            await db.flush()
            for r in range(rows):
                rl = chr(ord("A") + r)
                for n in range(1, cols + 1):
                    code = f"{rl}-{n}"
                    s = Seat(
                        id=f"{h.id}:{code}", code=code, hall_id=h.id,
                        library_id=lib.id, branch_id=main.id, row=rl, number=n,
                        status=SeatStatus.available,
                    )
                    db.add(s)
                    seat_by_code.setdefault(code, s)  # first hall wins for demo seat codes

        # A few reserved / maintenance seats for visual variety.
        for code in ("A-5", "B-3", "C-9"):
            if code in seat_by_code:
                seat_by_code[code].status = SeatStatus.reserved
        for code in ("E-2", "D-8"):
            if code in seat_by_code:
                seat_by_code[code].status = SeatStatus.maintenance

        # Students.
        for sid, name, phone, plan_name, seat_code, due, joined, batch_name in STUDENTS:
            plan = plan_by_name[plan_name]
            start = date.fromisoformat(joined)
            end = start + timedelta(days=PERIOD_DAYS.get(PERIOD[plan_name], 365))
            stu = Student(
                id=sid, library_id=lib.id, branch_id=main.id, name=name, phone=phone,
                plan_id=plan.id, batch_id=batch_by_name[batch_name].id,
                due_amount=due, joined_date=start, membership_start=start, membership_end=end,
            )
            db.add(stu)
            await db.flush()
            if seat_code and seat_code in seat_by_code:
                seat = seat_by_code[seat_code]
                seat.status = SeatStatus.occupied
                seat.student_id = sid
                seat.occupied_since = "9:05 AM"
                stu.seat_id = seat.id
                stu.hall_id = seat.hall_id

        # A couple of payments + attendance + notifications for the dashboard.
        db.add(Payment(
            id="INV-4821", library_id=lib.id, branch_id=main.id, student_id="2790",
            plan_id=plan_by_name["Premium"].id, date=date.today(), method=PaymentMethod.UPI,
            amount=9000, gst=1620, status=PaymentStatus.paid, description="Premium Annual renewal",
        ))
        db.add(AttendanceLog(
            library_id=lib.id, branch_id=main.id, student_id="2841", date=date.today(),
            check_in_at=datetime.now(timezone.utc), method=AttendanceMethod.QR,
            status=AttendanceStatus.inside,
        ))
        db.add(Notification(
            library_id=lib.id, branch_id=main.id, student_id="2790", type=NotificationType.paid,
            channel=NotificationChannel.WhatsApp, message="Payment of ₹9,000 received. Receipt sent.",
            sent_at=datetime.now(timezone.utc), read=False,
        ))

        # Extra staff members (multiple roles) for the Staff tab.
        for name, email, role, br_idx in [
            ("Anita Desai", "anita@studyhub.in", StaffRole.Manager, 0),
            ("Suresh Kumar", "suresh@studyhub.in", StaffRole.FrontDesk, 0),
            ("Latha Raman", "latha@studyhub.in", StaffRole.Accountant, 0),
            ("Vivek Nair", "vivek@studyhub.in", StaffRole.Manager, 1),
        ]:
            db.add(Staff(
                library_id=lib.id, branch_id=branches[br_idx].id, name=name, email=email,
                hashed_password=hash_password("changeme123"), role=role, active=True,
            ))

        # Inventory / assets for the Inventory tab.
        from app.models.enums import AssetStatus
        from app.models.inventory import Asset
        for aname, cat, qty, status, loc, cost in [
            ("Study Chairs", "Furniture", 180, AssetStatus.in_use, "All halls", 1200),
            ("Study Tables", "Furniture", 90, AssetStatus.in_use, "All halls", 3500),
            ("Desktop Computers", "Electronics", 24, AssetStatus.in_use, "Computer Lab", 32000),
            ("Air Conditioners", "Electronics", 8, AssetStatus.in_use, "Ground & First Floor", 42000),
            ("CCTV Cameras", "Security", 12, AssetStatus.in_use, "All floors", 4500),
            ("Reading Lamps", "Furniture", 60, AssetStatus.available, "Storage", 800),
            ("UPS Battery Backup", "Electronics", 3, AssetStatus.maintenance, "Server room", 18000),
            ("Water Purifiers", "Appliances", 4, AssetStatus.in_use, "Each floor", 15000),
            ("Old Projector", "Electronics", 1, AssetStatus.retired, "Storage", 22000),
            ("Fire Extinguishers", "Security", 10, AssetStatus.in_use, "All floors", 2500),
        ]:
            db.add(Asset(
                library_id=lib.id, branch_id=main.id, name=aname, category=cat, quantity=qty,
                status=status, location=loc, unit_cost=cost, purchase_date=date(2025, 6, 1),
            ))

        # Platform admin (SaaS operator) + approve the demo library.
        from app.models.admin import PlatformAdmin
        from app.models.enums import LibraryStatus
        lib.status = LibraryStatus.approved
        lib.plan = "Premium"
        lib.owner_name = "Rahul Krishnan"
        lib.email = "owner@studyhub.in"
        existing_admin = (await db.execute(select(PlatformAdmin).where(PlatformAdmin.email == "admin@libradesk.com"))).scalar_one_or_none()
        if not existing_admin:
            db.add(PlatformAdmin(
                name="LibraDesk Admin", email="admin@libradesk.com",
                hashed_password=hash_password("admin123"), active=True,
            ))

        # A couple of PENDING / sample libraries so the admin console has data.
        for iname, owner, email, phone, plan, city, st in [
            ("Scholars Den Library", "Meera Pillai", "meera@scholarsden.in", "+91 98400 12345", "Starter", "Coimbatore", LibraryStatus.pending),
            ("FocusHub Study Center", "Arjun Menon", "arjun@focushub.in", "+91 90030 67890", "Premium", "Madurai", LibraryStatus.pending),
            ("QuietCorner Reading Room", "Divya Rao", "divya@quietcorner.in", "+91 99520 55221", "Starter", "Trichy", LibraryStatus.approved),
        ]:
            pend = Library(
                name=iname, owner_name=owner, email=email, contact_phone=phone,
                address=city, plan=plan, status=st, accent_color="#0f7c5a",
            )
            db.add(pend)
            await db.flush()
            pb = Branch(library_id=pend.id, name="Main Branch", area=city)
            db.add(pb)
            await db.flush()
            db.add(BranchSettings(branch_id=pb.id))
            db.add(Staff(
                library_id=pend.id, branch_id=pb.id, name=owner, email=email,
                hashed_password=hash_password("changeme123"), role=StaffRole.Owner, active=True,
            ))

        await db.commit()
        print(f"Seeded library {lib.id} with {len(STUDENTS)} students across {len(branches)} branches.")
        print("Login:  owner@studyhub.in  /  studyhub123")


if __name__ == "__main__":
    asyncio.run(seed())
