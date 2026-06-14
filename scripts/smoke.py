import asyncio
from collections import Counter

import httpx

from app.main import app


async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        print("health:", (await c.get("/health")).json())
        r = await c.post(
            "/api/v1/auth/login",
            data={"username": "owner@studyhub.in", "password": "studyhub123"},
        )
        tok = r.json()["access_token"]
        print("login: token len", len(tok))
        H = {"Authorization": f"Bearer {tok}"}
        me = (await c.get("/api/v1/auth/me", headers=H)).json()
        print("me:", me["name"], me["role"])
        k = (await c.get("/api/v1/dashboard", headers=H)).json()["kpis"]
        print(
            "KPIs: total=%s active=%s expired=%s seats=%s avail=%s occ=%.2f todayRev=%s monthRev=%s pendStu=%s gst=%s"
            % (
                k["total_students"], k["active_students"], k["expired_memberships"],
                k["total_seats"], k["available_seats"], k["occupancy_rate"],
                k["today_revenue"], k["monthly_revenue"], k["pending_students"], k["gst_collected"],
            )
        )
        sj = (await c.get("/api/v1/students?page=1&page_size=5", headers=H)).json()
        print("students total=%s first=%s status=%s batch=%s" % (
            sj["total"], sj["items"][0]["name"], sj["items"][0]["status"], sj["items"][0]["batch_name"]))
        due = (await c.get("/api/v1/students?status=due", headers=H)).json()
        print("due students:", [s["name"] for s in due["items"]])
        halls = (await c.get("/api/v1/halls", headers=H)).json()
        print("halls:", [(h["name"], h["capacity"]) for h in halls])
        seats = (await c.get(f"/api/v1/seats?hall_id={halls[0]['id']}", headers=H)).json()
        print("hall A status counts:", dict(Counter(s["status"] for s in seats)))
        plans = (await c.get("/api/v1/plans", headers=H)).json()
        batches = (await c.get("/api/v1/batches", headers=H)).json()
        new = await c.post("/api/v1/students", headers=H, json={
            "name": "Test User", "phone": "+91 90000 00000",
            "plan_id": plans[0]["id"], "batch_id": batches[0]["id"], "hall_id": halls[0]["id"]})
        print("onboard ->", new.status_code, new.json()["id"], new.json()["status"], "seat=", new.json()["seat_id"] is not None)
        pay = await c.post("/api/v1/payments", headers=H, json={
            "student_id": new.json()["id"], "amount": 18000, "method": "UPI"})
        print("payment ->", pay.status_code, pay.json()["id"], "gst=", pay.json()["gst"])
        nc = (await c.get("/api/v1/notifications/unread-count", headers=H)).json()
        print("unread notifs:", nc["unread"])
        print("openapi paths:", len((await c.get("/api/v1/openapi.json")).json()["paths"]))


if __name__ == "__main__":
    asyncio.run(main())
