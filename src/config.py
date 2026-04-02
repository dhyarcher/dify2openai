import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Dify API base URL (without trailing slash)
DIFY_BASE_URL: str = os.getenv("DIFY_BASE_URL", "https://api.dify.ai")

# Default input fields sent to Dify for every request.
# Set via a JSON string in the env var, e.g.:
#   DIFY_INPUTS_DEFAULTS='{"customField": "value"}'
# If unset, an empty dict is used (no extra inputs sent).
_raw_inputs = os.getenv("DIFY_INPUTS_DEFAULTS", "{}")
try:
    DIFY_INPUTS_DEFAULTS: dict = json.loads(_raw_inputs)
    if not isinstance(DIFY_INPUTS_DEFAULTS, dict):
        raise ValueError("DIFY_INPUTS_DEFAULTS must be a JSON object")
except (json.JSONDecodeError, ValueError) as e:
    import warnings
    warnings.warn(f"Invalid DIFY_INPUTS_DEFAULTS env var, using empty dict: {e}")
    DIFY_INPUTS_DEFAULTS = {}
