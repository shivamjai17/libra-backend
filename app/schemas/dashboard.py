from pydantic import BaseModel


class Kpis(BaseModel):
    total_students: int
    active_students: int
    expired_memberships: int
    total_seats: int
    available_seats: int
    occupancy_rate: float
    today_attendance: int
    inside_now: int
    today_revenue: int
    monthly_revenue: int
    pending_payments: int
    pending_students: int
    gst_collected: int


class DashboardWidgets(BaseModel):
    upcoming_expirations: list[dict]
    pending_dues: list[dict]
    recent_registrations: list[dict]
    recent_payments: list[dict]
    recent_activity: list[dict]


class DashboardOut(BaseModel):
    kpis: Kpis
    widgets: DashboardWidgets


class AnalyticsOut(BaseModel):
    retention_rate: float
    renewal_rate: float
    net_growth: int
    revenue_forecast: list[dict]
    peak_hours: list[dict]
    branch_performance: list[dict]
    payment_method_breakdown: list[dict]
