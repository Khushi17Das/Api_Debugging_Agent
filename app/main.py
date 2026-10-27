import os
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.database import init_db
from app.routes.debug import router as debug_router
from app.routes.history import router as history_router
from app.routes.sample_broken import router as sample_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes SQLite database tables upon server startup."""
    init_db()
    yield


app = FastAPI(
    title="API Debugging Agent",
    description="AI-powered diagnostic and fix generation assistant for API developers with Smart Fallback Mode.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ZeroDivisionError)
async def zero_division_exception_handler(request: Request, exc: ZeroDivisionError):
    tb = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content={
            "error": "ZeroDivisionError",
            "message": "division by zero",
            "traceback": tb,
        },
    )

app.include_router(debug_router)
app.include_router(history_router)
app.include_router(sample_router)


@app.get("/api/health", tags=["Health"])
def health_check():
    """Health check endpoint for liveness and readiness probes."""
    return {
        "status": "healthy",
        "service": "API Debugging Agent",
        "version": "1.0.0",
        "features": [
            "Smart Fallback Mode",
            "Evidence-Based Diagnosis",
            "Safe Fix Mode",
            "Endpoint Testing",
            "Fix Verification",
            "SQLite Session History",
        ],
    }


# Mount frontend static files and root HTML route
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main.py:app", host=host, port=port, reload=True)
