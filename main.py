from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from dotenv import load_dotenv
from pdf_generator import generate_invoice_pdf, PRICE_PER_M2
import os, io
from datetime import datetime

load_dotenv()

app = FastAPI(title="Sky Legends API", version="1.0.0")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Auth ─────────────────────────────────────────────────────────────────────

def require_admin(x_admin_key: str = Header(default=None)):
    if ADMIN_API_KEY and x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ─── Models ───────────────────────────────────────────────────────────────────

class OrderRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str
    company: str = ""
    ico: str = ""
    billing_address: str
    location: str
    building_type: str = "office"
    floors: int = 1
    facade_area: float
    window_area: float
    service_date: str = ""
    notes: str = ""

class StatusUpdate(BaseModel):
    status: str

# ─── Helpers ──────────────────────────────────────────────────────────────────

def gen_order_num() -> str:
    res = supabase.table("orders").select("order_num").order("order_num", desc=True).limit(1).execute()
    if res.data:
        last_num = res.data[0]["order_num"]  # e.g. "AW-000014"
        n = int(last_num.split("-")[1]) + 1
    else:
        n = 1
    return f"AW-{n:06d}"

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/orders", status_code=201)
async def create_order(req: OrderRequest):
    # 1. Upsert client
    client_payload = {
        "name": req.name,
        "email": req.email,
        "phone": req.phone,
        "company": req.company,
        "ico": req.ico,
        "billing_address": req.billing_address,
    }
    client_res = supabase.table("clients").upsert(
        client_payload, on_conflict="email"
    ).execute()
    if not client_res.data:
        raise HTTPException(500, "Failed to save client")
    client_id = client_res.data[0]["id"]

    # 2. Generate order number
    order_num = gen_order_num()

    # 3. Insert order
    order_payload = {
        "order_num": order_num,
        "client_id": client_id,
        "location": req.location,
        "building_type": req.building_type,
        "floors": req.floors,
        "facade_area": req.facade_area,
        "window_area": req.window_area,
        "service_date": req.service_date or None,
        "notes": req.notes,
        "status": "new",
    }
    order_res = supabase.table("orders").insert(order_payload).execute()
    if not order_res.data:
        raise HTTPException(500, "Failed to save order")
    order = order_res.data[0]

    # 4. Generate PDF + upload (both non-fatal)
    pdf_url = None
    try:
        pdf_bytes = generate_invoice_pdf(order, client_payload)
        storage_path = f"invoices/{order_num}.pdf"
        supabase.storage.from_("invoices").upload(
            storage_path, pdf_bytes, {"content-type": "application/pdf"}
        )
        pdf_url = supabase.storage.from_("invoices").get_public_url(storage_path)
        supabase.table("orders").update({"pdf_url": pdf_url}).eq("id", order["id"]).execute()
    except Exception as e:
        print(f"[PDF] non-fatal error for {order_num}: {e}")

    total = (req.facade_area + req.window_area) * PRICE_PER_M2

    return {
        "order_num": order_num,
        "total": total,
        "pdf_url": pdf_url,
        "client_id": client_id,
    }


@app.get("/orders", dependencies=[Depends(require_admin)])
async def list_orders(status: str = None, limit: int = 100, offset: int = 0):
    q = supabase.table("orders").select("*, clients(name,email,phone,company)").order(
        "created_at", desc=True
    ).limit(limit).offset(offset)
    if status:
        q = q.eq("status", status)
    res = q.execute()
    return {"data": res.data, "count": len(res.data)}


@app.get("/orders/{order_num}", dependencies=[Depends(require_admin)])
async def get_order(order_num: str):
    res = supabase.table("orders").select("*, clients(*)").eq("order_num", order_num).single().execute()
    if not res.data:
        raise HTTPException(404, "Order not found")
    return res.data


@app.patch("/orders/{order_num}/status", dependencies=[Depends(require_admin)])
async def update_status(order_num: str, body: StatusUpdate):
    allowed = {"new", "confirmed", "in_progress", "completed", "cancelled"}
    if body.status not in allowed:
        raise HTTPException(400, f"Status must be one of {allowed}")
    supabase.table("orders").update({"status": body.status}).eq("order_num", order_num).execute()
    return {"ok": True}


@app.get("/orders/{order_num}/pdf")
async def download_pdf(order_num: str):
    res = supabase.table("orders").select("*, clients(*)").eq("order_num", order_num).single().execute()
    if not res.data:
        raise HTTPException(404, "Order not found")
    order = res.data
    client = order.pop("clients", {})
    pdf_bytes = generate_invoice_pdf(order, client)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=nabidka-{order_num}.pdf"},
    )




@app.delete("/orders/{order_num}", dependencies=[Depends(require_admin)])
async def delete_order(order_num: str):
    res = supabase.table("orders").select("id").eq("order_num", order_num).single().execute()
    if not res.data:
        raise HTTPException(404, "Order not found")
    supabase.table("orders").delete().eq("order_num", order_num).execute()
    return {"ok": True}


@app.get("/clients", dependencies=[Depends(require_admin)])
async def list_clients(limit: int = 100):
    res = supabase.table("clients").select("*, orders(count)").order("created_at", desc=True).limit(limit).execute()
    return {"data": res.data}


@app.get("/stats", dependencies=[Depends(require_admin)])
async def get_stats():
    orders = supabase.table("orders").select("total_price,total_area,status").execute().data
    clients = supabase.table("clients").select("id", count="exact").execute()
    by_status = {}
    for o in orders:
        s = o.get("status", "new")
        by_status[s] = by_status.get(s, 0) + 1
    return {
        "total_orders": len(orders),
        "total_clients": clients.count or 0,
        "total_area": sum(float(o.get("total_area") or 0) for o in orders),
        "total_revenue": sum(float(o.get("total_price") or 0) for o in orders),
        "by_status": by_status,
    }
