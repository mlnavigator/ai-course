"""Готовый API доставки. Студенты вызывают его по HTTP из своего MCP-сервера."""
from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Учебный API доставки", version="1.0")
Status = Literal["created", "in_transit", "delivered"]

# При перезапуске процесса изменения сбрасываются.
SHIPMENTS = {
    101: {"order_id": 101, "status": "delivered", "city": "Кострома", "planned_date": "2026-10-03"},
    102: {"order_id": 102, "status": "in_transit", "city": "Ярославль", "planned_date": "2026-10-11"},
    104: {"order_id": 104, "status": "created", "city": "Кострома", "planned_date": "2026-10-12"},
    107: {"order_id": 107, "status": "created", "city": "Кострома", "planned_date": "2026-10-13"},
}


class QuoteRequest(BaseModel):
    weight_grams: int = Field(gt=0, le=30000)
    zone: Literal["local", "regional"]


class RescheduleRequest(BaseModel):
    planned_date: date


@app.get("/health")
def health():
    return {"status": "ok", "service": "delivery-demo"}


@app.get("/shipments")
def list_shipments(status: Status | None = None):
    return {"shipments": [s.copy() for s in SHIPMENTS.values()
                          if status is None or s["status"] == status]}


@app.get("/shipments/{order_id}")
def get_shipment(order_id: int):
    if order_id not in SHIPMENTS:
        raise HTTPException(404, "Доставка для этого заказа не найдена")
    return SHIPMENTS[order_id].copy()


@app.post("/shipping/quote")
def shipping_quote(body: QuoteRequest):
    # Начатые килограммы округляются вверх. Деньги — целые копейки.
    kg = (body.weight_grams + 999) // 1000
    base = 15000 if body.zone == "local" else 30000
    return {"price_kopecks": base + 5000 * kg, "currency": "RUB"}


@app.post("/shipments/{order_id}/reschedule")
def reschedule(order_id: int, body: RescheduleRequest):
    shipment = get_shipment(order_id)
    if shipment["status"] == "delivered":
        raise HTTPException(409, "Доставленный заказ нельзя перенести")
    # Фиксированная дата учебного сценария, а не текущая дата компьютера.
    if body.planned_date < date(2026, 10, 10):
        raise HTTPException(422, "В демо дата должна быть не раньше 2026-10-10")
    SHIPMENTS[order_id]["planned_date"] = body.planned_date.isoformat()
    return SHIPMENTS[order_id].copy()
