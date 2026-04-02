"""
Dify API request/response schemas.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any, Literal

from src.config import DIFY_INPUTS_DEFAULTS


class DifyFile(BaseModel):
    type: str = "image"
    transfer_method: Literal["remote_url", "local_file"] = "remote_url"
    url: Optional[str] = None


class DifyInputs(BaseModel):
    """
    Dynamic input fields for Dify workflow.

    No fields are hardcoded here. All fields and their default values are
    configured externally via the DIFY_INPUTS_DEFAULTS environment variable
    (a JSON object), loaded at startup from src.config.

    The `tools` field is always present and holds the JSON-serialized list of
    OpenAI-compatible tool definitions passed in the original request.

    Callers can also pass extra keyword arguments to override specific fields
    for a given request.
    """
    model_config = ConfigDict(extra="allow")

    # Always-present: serialized JSON array of tool definitions from the OpenAI request.
    # Defaults to an empty list when the caller provides no tools.
    tools: Any = Field(default_factory=list)

    @classmethod
    def from_defaults(cls, **overrides: Any) -> "DifyInputs":
        """Create an instance seeded with DIFY_INPUTS_DEFAULTS, then apply any overrides."""
        return cls(**{**DIFY_INPUTS_DEFAULTS, **overrides})


class DifyChatRequest(BaseModel):
    inputs: DifyInputs = Field(default_factory=DifyInputs.from_defaults)
    # query holds the full conversation history as a JSON string (list of {role, content} objects)
    query: str
    response_mode: Literal["streaming", "blocking"] = "streaming"
    conversation_id: str = ""
    user: str = "default-user"
    files: List[DifyFile] = []
