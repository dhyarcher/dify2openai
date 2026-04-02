"""
FastAPI router for OpenAI-compatible Chat Completions endpoint.

Supports two routing modes:
  1. Global route  — POST /v1/chat/completions
     Uses DIFY_BASE_URL env var + Bearer token as the API key.

  2. Per-API route — POST /apis/{api_id}/v1/chat/completions
     Uses the stored base_url + api_key from the API Manager record.
     The Bearer token is still accepted (overrides stored key when provided).
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from src.schemas.openai_schemas import ChatCompletionRequest
from src.schemas.dify_schemas import DifyInputs
from src.services.dify_service import (
    convert_openai_to_dify,
    stream_dify_response,
    call_dify_blocking,
)
from src import api_manager

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_api_key(request: Request) -> str | None:
    """Extract API key from Authorization header (Bearer token). Returns None if absent."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):]
    return None


def _require_api_key(request: Request) -> str:
    key = _extract_api_key(request)
    if not key:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Expected: Bearer {api_key}",
        )
    return key


# ── Global Route ──────────────────────────────────────────────────────────────

@router.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    """
    Global OpenAI-compatible Chat Completions endpoint.

    Accepts standard OpenAI request format and proxies to the Dify API
    configured via environment variables.
    The Authorization Bearer token is forwarded as the Dify API key.
    """
    api_key = _require_api_key(request)
    dify_request = convert_openai_to_dify(body)

    if body.stream:
        return StreamingResponse(
            stream_dify_response(dify_request, api_key),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        result = await call_dify_blocking(dify_request, api_key)
        return JSONResponse(content=result.model_dump())


# ── Per-API Route ─────────────────────────────────────────────────────────────

@router.post("/apis/{api_id}/v1/chat/completions")
async def chat_completions_by_api(
    api_id: str, body: ChatCompletionRequest, request: Request
):
    """
    Per-API OpenAI-compatible Chat Completions endpoint.

    Routes to the specific Dify app configured in the API Manager.
    The stored api_key is used by default; pass a Bearer token to override it.
    """
    record = api_manager.get_api(api_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"API '{api_id}' not found.")

    # Bearer token overrides the stored key (allows per-request key injection)
    bearer = _extract_api_key(request)
    api_key = bearer or record["api_key"]
    base_url = record["base_url"]

    # Build the Dify request using stored default inputs
    from src.schemas.dify_schemas import DifyChatRequest
    import json as _json

    # Serialize the full conversation history as a JSON string for Dify query
    messages_payload = [
        {"role": msg.role, "content": msg.content}
        for msg in body.messages
    ]
    query = _json.dumps(messages_payload, ensure_ascii=False)

    # Collect tools from the OpenAI request
    tools_payload = []
    if hasattr(body, "tools") and body.tools:
        tools_payload = [
            t.model_dump() if hasattr(t, "model_dump") else t
            for t in body.tools
        ]

    stored_inputs = dict(record.get("inputs", {}))
    stored_inputs["tools"] = tools_payload

    dify_request = DifyChatRequest(
        inputs=DifyInputs(**stored_inputs),
        query=query,
        response_mode="streaming" if body.stream else "blocking",
        conversation_id="",
        user=body.user or "default-user",
        files=[],
    )

    if body.stream:
        return StreamingResponse(
            stream_dify_response(dify_request, api_key, dify_url=base_url),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        result = await call_dify_blocking(dify_request, api_key, dify_url=base_url)
        return JSONResponse(content=result.model_dump())
