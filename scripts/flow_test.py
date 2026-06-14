import asyncio
import httpx
from app.main import app


async def main():
    t = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=t, base_url="http://x") as c:
        tok = (await c.post("/api/v1/auth/login", data={"username": "owner@studyhub.in", "password": "studyhub123"})).json()["access_token"]
        H = {"Authorization": f"Bearer {tok}"}

        # 1. Admin configures a new PLAN, BATCH, HALL in settings
        plan = (await c.post("/api/v1/plans", headers=H, json={"name": "Night Owl", "price": 12000, "period": "year", "seat_included": True})).json()
        print("created plan:", plan["name"], plan["id"][:8])
        batch = (await c.post("/api/v1/batches", headers=H, json={"name": "Night", "start_time": "21:00", "end_time": "23:59", "color": "purple"})).json()
        print("created batch:", batch["name"])
        hall = (await c.post("/api/v1/halls", headers=H, json={"name": "Night Hall", "floor": "Third Floor", "rows": 2, "cols": 5})).json()
        print("created hall:", hall["name"], "capacity:", hall["capacity"])

        # 2. Those admin-configured items are now AVAILABLE for assignment
        plans = [p["name"] for p in (await c.get("/api/v1/plans", headers=H)).json()]
        batches = [b["name"] for b in (await c.get("/api/v1/batches", headers=H)).json()]
        halls = [h["name"] for h in (await c.get("/api/v1/halls", headers=H)).json()]
        print("plans now:", plans)
        print("batches now:", batches)
        print("halls now:", halls)

        # 3. Onboard a student USING the newly-configured plan/batch/hall -> seat auto-assigned from that hall
        stu = (await c.post("/api/v1/students", headers=H, json={
            "name": "Night Student", "phone": "+91 90000 22222",
            "plan_id": plan["id"], "batch_id": batch["id"], "hall_id": hall["id"]})).json()
        print("onboarded:", stu["id"], "plan:", stu["plan_name"], "batch:", stu["batch_name"], "seat:", stu["seat_id"])
        assigned_hall = stu["seat_id"].split(":")[0] if stu["seat_id"] else None
        print("seat is from the new hall:", assigned_hall == hall["id"])

        # 4. Delete a plan/batch/hall (settings CRUD)
        dp = await c.delete(f"/api/v1/plans/{plan['id']}", headers=H)
        db = await c.delete(f"/api/v1/batches/{batch['id']}", headers=H)
        dh = await c.delete(f"/api/v1/halls/{hall['id']}", headers=H)
        print("delete status (plan/batch/hall):", dp.status_code, db.status_code, dh.status_code)
        halls_after = [h["name"] for h in (await c.get("/api/v1/halls", headers=H)).json()]
        print("halls after delete:", halls_after)


if __name__ == "__main__":
    asyncio.run(main())
