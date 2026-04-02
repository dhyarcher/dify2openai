"""
OpenAI-compatible request/response schemas for Chat Completions API.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional, List, Literal, Union


# ── Request Models ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    # Accept plain string OR OpenAI multimodal array: [{"type": "text", "text": "..."}]
    content: Union[str, List[Any]]

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, v: Any) -> str:
        """
        Flatten multimodal content arrays into a plain string.
        LiteLLM and newer OpenAI clients sometimes send:
            "content": [{"type": "text", "text": "..."}, ...]
        We extract and join all text parts.
        """
        if isinstance(v, list):
            parts = []
            for part in v:
                if isinstance(part, dict):
                    # Standard OpenAI content-part object
                    if part.get("type") == "text":
                        parts.append(part.get("text", ""))
                    elif "text" in part:
                        parts.append(part["text"])
                elif isinstance(part, str):
                    parts.append(part)
            return "".join(parts)
        return v


class ChatCompletionRequest(BaseModel):
    model: str = "dify"
    messages: List[ChatMessage]
    stream: bool = True
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    user: Optional[str] = None


# ── Streaming Response Models (SSE chunks) ──────────────────────────────────

class DeltaContent(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class Choice(BaseModel):
    index: int = 0
    delta: DeltaContent
    logprobs: Optional[object] = None
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str = ""
    object: str = "chat.completion.chunk"
    created: int = 0
    model: str = ""
    choices: List[Choice] = []


# ── Non-streaming Response Models ───────────────────────────────────────────

class MessageContent(BaseModel):
    role: str = "assistant"
    content: str = ""


class CompletionChoice(BaseModel):
    index: int = 0
    message: MessageContent
    logprobs: Optional[object] = None
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str = ""
    object: str = "chat.completion"
    created: int = 0
    model: str = ""
    choices: List[CompletionChoice] = []
    usage: UsageInfo = UsageInfo()
