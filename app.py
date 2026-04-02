"""
OpenAI-to-Dify Proxy — Application Entry Point.

Mounts:
  - FastAPI  → /          (OpenAI-compatible API proxy)
  - Gradio   → /ui        (API Manager dashboard)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr

from src.routers.chat import router as chat_router
from gradio_ui import build_ui, _THEME, CUSTOM_CSS

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Dify2OpenAI Proxy",
    description=(
        "Proxy server that accepts OpenAI-compatible requests and forwards them to Dify API. "
        "Visit /ui for the API Manager dashboard."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/apis", tags=["API Manager"])
async def list_apis_endpoint():
    """List all registered API proxies (JSON)."""
    from src import api_manager
    return {"apis": api_manager.list_apis()}


# ── Gradio UI ─────────────────────────────────────────────────────────────────
gradio_app = build_ui()

# Mount Gradio at /ui (Gradio 6.x: theme/css go into mount_gradio_app)
app = gr.mount_gradio_app(
    app,
    gradio_app,
    path="/ui",
    theme=_THEME,
    css=CUSTOM_CSS,
)
