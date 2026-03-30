from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import auth, admin, users, buildings, files, chat, dashboard, billing, doc_ai, mail_drafting, db_health, services
from app.core.database import init_db
from app.core.logging_config import setup_logging


app = FastAPI(
    title="APT Portfolio Pulse Services")

app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
    
@app.on_event("startup")
async def on_startup():
    await init_db()
    setup_logging()


@app.on_event("shutdown")
async def on_shutdown():
    pass


# Include routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(billing.router)
app.include_router(users.router)
app.include_router(buildings.router)
app.include_router(files.router)
app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(doc_ai.router)
app.include_router(mail_drafting.router)
app.include_router(services.router)
app.include_router(db_health.router)
