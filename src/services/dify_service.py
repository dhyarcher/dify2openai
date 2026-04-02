"""
Service layer for converting OpenAI requests to Dify format and calling Dify API.
"""

import json
import re
import time
import uuid
import httpx
from typing import AsyncGenerator

from src.schemas.openai_schemas import (
    ChatCompletionRequest,
    ChatCompletionChunk,
    ChatCompletionResponse,
    Choice,
    CompletionChoice,
    DeltaContent,
    MessageContent,
    UsageInfo,
)
from src.schemas.dify_schemas import DifyChatRequest, DifyInputs, DifyFile
from src.config import DIFY_BASE_URL


def clean_answer(answer: str) -> str:
    """Filter out unwanted tokens from the model answer."""
    if not answer:
        return ""

    # Strip leading bracket prefix like "[something]"
    if answer.startswith('[') and ']' in answer:
        first_bracket = answer.find(']')
        answer = answer[first_bracket + 1:]

    # Remove <show>...</show> blocks
    answer = re.sub(r'<show>.*?</show>', '', answer, flags=re.DOTALL)

    # Remove <|start_think|>...</|finish_think|> blocks
    answer = re.sub(r'<\|start_think\|>.*?<\|finish_think\|>', '', answer, flags=re.DOTALL)

    # Remove <checklist>...</checklist> blocks
    answer = re.sub(r'<checklist>.*?</checklist>', '', answer, flags=re.DOTALL)

    # Normalize escaped newlines
    answer = answer.replace('\\n', '\n')

    # Collapse 3+ consecutive newlines down to 2
    answer = re.sub(r'\n{3,}', '\n\n', answer)

    return answer.strip()


def convert_openai_to_dify(request: ChatCompletionRequest) -> DifyChatRequest:
    """
    Convert an OpenAI Chat Completion request to a Dify chat-messages request.

    - Serializes the full messages list (all roles/content) as a JSON string
      and passes it to the `query` field so Dify receives the complete context.
    - Tools from the OpenAI request are forwarded to DifyInputs.tools.
    - Input fields are additionally populated from DIFY_INPUTS_DEFAULTS (env var).
    - Maps stream flag to Dify response_mode.
    """
    # Serialize the full conversation history as a JSON string for Dify query
    messages_payload = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages
    ]
    query = json.dumps(messages_payload, ensure_ascii=False)

    # Collect tools from the OpenAI request (may be None or a list of tool dicts)
    tools_payload = []
    if request.tools:
        tools_payload = [
            t.model_dump() if hasattr(t, "model_dump") else t
            for t in request.tools
        ]

    # Build Dify request — inputs seeded from DIFY_INPUTS_DEFAULTS, tools always included
    dify_request = DifyChatRequest(
        inputs=DifyInputs.from_defaults(tools=tools_payload),
        query=query,
        response_mode="streaming" if request.stream else "blocking",
        conversation_id="",
        user=request.user or "default-user",
        files=[],
    )

    return dify_request



def _generate_chunk_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:12]}"


def _build_openai_sse_chunk(
    chunk_id: str,
    content: str = "",
    role: str | None = None,
    finish_reason: str | None = None,
    model: str = "dify",
) -> str:
    """Build an OpenAI-compatible SSE data line."""
    chunk = ChatCompletionChunk(
        id=chunk_id,
        object="chat.completion.chunk",
        created=int(time.time()),
        model=model,
        choices=[
            Choice(
                index=0,
                delta=DeltaContent(role=role, content=content),
                finish_reason=finish_reason,
            )
        ],
    )
    return f"data: {chunk.model_dump_json()}\n\n"


async def stream_dify_response(
    dify_request: DifyChatRequest,
    api_key: str,
    dify_url: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Call Dify API in streaming mode and yield OpenAI-compatible SSE chunks.
    
    Parses Dify SSE events (data: {...}) and converts them
    to OpenAI chat.completion.chunk format.
    """
    url = f"{dify_url or DIFY_BASE_URL}/v1/chat-messages"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = dify_request.model_dump()

    chunk_id = _generate_chunk_id()

    # Send initial role chunk
    yield _build_openai_sse_chunk(chunk_id, content="", role="assistant")

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        async with client.stream(
            "POST", url, json=payload, headers=headers
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                line = line.strip()

                if not line:
                    continue

                # Parse SSE data
                if line.startswith("data:"):
                    data_str = line[len("data:"):].strip()

                    try:
                        data = json.loads(data_str)
                        event = data.get("event")
                    except json.JSONDecodeError:
                        continue

                    if event == "message":
                        answer = clean_answer(data.get("answer", ""))
                        if answer:
                            yield _build_openai_sse_chunk(chunk_id, content=answer)
                    elif event == "message_replace":
                        # Dify's message_replace event typically contains the full new message.
                        # For OpenAI compatibility, we treat it as a new content chunk.
                        answer = clean_answer(data.get("answer", ""))
                        if answer:
                            yield _build_openai_sse_chunk(chunk_id, content=answer)
                    elif event == "message_end":
                        # Send finish chunk
                        yield _build_openai_sse_chunk(
                            chunk_id, content="", finish_reason="stop"
                        )
                        yield "data: [DONE]\n\n"
                        return
                    elif event == "error":
                        error_msg = data.get("message", "Unknown Dify error")
                        yield _build_openai_sse_chunk(
                            chunk_id, content=f"\n[Error] {error_msg}"
                        )
                        yield _build_openai_sse_chunk(
                            chunk_id, content="", finish_reason="stop"
                        )
                        yield "data: [DONE]\n\n"
                        return
                    elif event in [
                        "node_started",
                        "node_finished",
                        "workflow_started",
                        "workflow_finished",
                        "ping",
                        "tts_message",
                        "tts_message_end",
                        "message_file",
                    ]:
                        # These events are Dify-specific and don't directly map to
                        # OpenAI chat completion content. We can ignore them for now.
                        pass
                    # Add other event types if needed for specific handling

    # Fallback: ensure stream ends properly
    yield _build_openai_sse_chunk(chunk_id, content="", finish_reason="stop")
    yield "data: [DONE]\n\n"


async def call_dify_blocking(
    dify_request: DifyChatRequest,
    api_key: str,
    dify_url: str | None = None,
) -> ChatCompletionResponse:
    """
    Call Dify API in blocking mode and return OpenAI-compatible JSON response.
    """
    url = f"{dify_url or DIFY_BASE_URL}/v1/chat-messages"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = dify_request.model_dump()

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    answer = clean_answer(data.get("answer", ""))

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        object="chat.completion",
        created=int(time.time()),
        model="dify",
        choices=[
            CompletionChoice(
                index=0,
                message=MessageContent(role="assistant", content=answer),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(
            prompt_tokens=data.get("metadata", {}).get("usage", {}).get("prompt_tokens", 0),
            completion_tokens=data.get("metadata", {}).get("usage", {}).get("completion_tokens", 0),
            total_tokens=data.get("metadata", {}).get("usage", {}).get("total_tokens", 0),
        ),
    )
