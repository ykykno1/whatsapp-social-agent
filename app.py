"""
app.py - שרת FastAPI עם Webhook לוואטסאפ
"""
import os
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from contextlib import asynccontextmanager
from database import init_db
from agent import process_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_verify_token")
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 מאתחל את הסוכן...")
    init_db()
    logger.info("✅ הסוכן מוכן!")
    yield

app = FastAPI(title="WhatsApp Social Media AI Agent", version="1.0.0", lifespan=lifespan)

async def send_whatsapp_message(to: str, message: str) -> bool:
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": message, "preview_url": False}
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(WHATSAPP_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        logger.info(f"✅ נשלח ל-{to}")
        return True
    logger.error(f"❌ שגיאה: {response.status_code} - {response.text}")
    return False

def extract_message_data(body):
    try:
        value = body["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return None, None
        msg = value["messages"][0]
        if msg.get("type") != "text":
            return msg["from"], None
        return msg["from"], msg["text"]["body"]
    except (KeyError, IndexError, TypeError):
        return None, None

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("✅ Webhook אומת!")
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
async def receive_message(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if body.get("object") != "whatsapp_business_account":
        return JSONResponse({"status": "ignored"})

    phone_number, message_text = extract_message_data(body)
    if not phone_number:
        return JSONResponse({"status": "ok"})
    if not message_text:
        await send_whatsapp_message(phone_number, "אני מקבל רק הודעות טקסט כרגע 😊")
        return JSONResponse({"status": "ok"})

    logger.info(f"📨 מ-{phone_number}: {message_text[:50]}...")
    reply = process_message(phone_number, message_text)

    if len(reply) > 4000:
        for i in range(0, len(reply), 4000):
            await send_whatsapp_message(phone_number, reply[i:i+4000])
    else:
        await send_whatsapp_message(phone_number, reply)

    return JSONResponse({"status": "ok"})

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "WhatsApp AI Agent 🚀"}
