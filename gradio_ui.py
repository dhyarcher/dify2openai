"""
Gradio UI — Dify2OpenAI API Manager

A beautiful dark-mode dashboard for creating and managing
OpenAI-compatible proxy endpoints backed by Dify apps.
"""

from __future__ import annotations

import json
from typing import Any

import gradio as gr

from src import api_manager


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_inputs(raw: str) -> dict:
    """Parse a JSON string into a dict; raise ValueError with friendly message."""
    raw = raw.strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Must be a JSON object, e.g. {\"key\": \"value\"}")
        return data
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc


def _mask_key(key: str) -> str:
    """Mask API key for display (show first 6 + last 4 chars)."""
    if len(key) <= 12:
        return "••••••••"
    return f"{key[:6]}{'•' * (len(key) - 10)}{key[-4:]}"


def _base_url_for_api(api_id: str, host: str = "http://localhost:8000") -> str:
    return f"{host}/apis/{api_id}"


# ── Create tab logic ──────────────────────────────────────────────────────────

def create_api_action(name: str, base_url: str, api_key: str, inputs_json: str):
    """Gradio callback: create a new API config."""
    try:
        inputs = _parse_inputs(inputs_json)
        record = api_manager.create_api(
            name=name,
            base_url=base_url,
            api_key=api_key,
            inputs=inputs,
        )
        endpoint = _base_url_for_api(record["id"])
        msg = (
            f"✅ **API '{record['name']}' created successfully!**\n\n"
            f"**ID (slug):** `{record['id']}`\n\n"
            f"**OpenAI-compatible endpoint:**\n```\n{endpoint}/v1/chat/completions\n```\n\n"
            f"Use `Authorization: Bearer {record['api_key']}` — or omit it to use the stored key."
        )
        return msg, gr.update(value=""), gr.update(value=""), gr.update(value=""), gr.update(value="")
    except ValueError as e:
        return f"❌ **Error:** {e}", gr.update(), gr.update(), gr.update(), gr.update()


# ── List tab logic ────────────────────────────────────────────────────────────

def _records_to_table(records: list[dict]) -> list[list[Any]]:
    rows = []
    for r in records:
        rows.append([
            r["id"],
            r["name"],
            r["base_url"],
            _mask_key(r["api_key"]),
            json.dumps(r.get("inputs", {}), ensure_ascii=False),
            r.get("created_at", "")[:19].replace("T", " "),
        ])
    return rows


def refresh_list():
    records = api_manager.list_apis()
    table = _records_to_table(records)
    count = f"**{len(records)} API(s) registered**"
    return table, count


def get_detail(api_id: str):
    if not api_id or not api_id.strip():
        return "⚠️ Please enter an API ID."
    record = api_manager.get_api(api_id.strip())
    if record is None:
        return f"❌ No API found with ID `{api_id}`."

    endpoint = _base_url_for_api(record["id"])
    inputs_pretty = json.dumps(record.get("inputs", {}), ensure_ascii=False, indent=2)
    detail = f"""## 📋 {record['name']}

| Field | Value |
|-------|-------|
| **ID** | `{record['id']}` |
| **Base URL** | `{record['base_url']}` |
| **API Key** | `{_mask_key(record['api_key'])}` |
| **Created** | {record.get('created_at', '')[:19].replace('T', ' ')} UTC |

**Default Inputs:**
```json
{inputs_pretty}
```

**Endpoint to use with OpenAI-compatible clients:**
```
POST {endpoint}/v1/chat/completions
Authorization: Bearer {record['api_key']}
Content-Type: application/json
```

**Example curl:**
```bash
curl -X POST "{endpoint}/v1/chat/completions" \\
  -H "Authorization: Bearer {record['api_key']}" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "model": "dify",
    "messages": [{{"role": "user", "content": "Hello!"}}],
    "stream": false
  }}'
```
"""
    return detail


# ── Delete logic ──────────────────────────────────────────────────────────────

def delete_api_action(api_id: str):
    if not api_id or not api_id.strip():
        return "⚠️ Please enter an API ID to delete.", *refresh_list()
    deleted = api_manager.delete_api(api_id.strip())
    if deleted:
        msg = f"🗑️ API `{api_id}` deleted successfully."
    else:
        msg = f"❌ No API found with ID `{api_id}`."
    table, count = refresh_list()
    return msg, table, count


# ── Edit logic ────────────────────────────────────────────────────────────────

def load_for_edit(api_id: str):
    if not api_id or not api_id.strip():
        return gr.update(), gr.update(), gr.update(), gr.update(), "⚠️ Enter an API ID to load."
    record = api_manager.get_api(api_id.strip())
    if record is None:
        return gr.update(), gr.update(), gr.update(), gr.update(), f"❌ No API found with ID `{api_id}`."
    inputs_str = json.dumps(record.get("inputs", {}), ensure_ascii=False, indent=2)
    return (
        gr.update(value=record["name"]),
        gr.update(value=record["base_url"]),
        gr.update(value=record["api_key"]),
        gr.update(value=inputs_str),
        f"✅ Loaded **{record['name']}** — edit fields below then click **Save Changes**."
    )


def save_edit_action(api_id: str, name: str, base_url: str, api_key: str, inputs_json: str):
    if not api_id or not api_id.strip():
        return "⚠️ Enter the API ID to update."
    try:
        inputs = _parse_inputs(inputs_json)
        api_manager.update_api(
            api_id=api_id.strip(),
            name=name or None,
            base_url=base_url or None,
            api_key=api_key or None,
            inputs=inputs if inputs_json.strip() else None,
        )
        return f"✅ API `{api_id}` updated successfully."
    except ValueError as e:
        return f"❌ **Error:** {e}"


# ── CSS ───────────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
/* ── Global ── */
body, .gradio-container {
    background: #0f1117 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* ── Tabs ── */
.tab-nav button {
    color: #94a3b8 !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.2s ease !important;
}
.tab-nav button.selected {
    color: #6366f1 !important;
    border-bottom-color: #6366f1 !important;
}

/* ── Inputs ── */
input, textarea, .gr-input, .gr-textarea {
    background: #1e2130 !important;
    border: 1px solid #2d3148 !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}
input:focus, textarea:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
}

/* ── Buttons ── */
.gr-button-primary {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}
.gr-button-primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(99,102,241,0.4) !important;
}
.gr-button-secondary {
    background: #1e2130 !important;
    border: 1px solid #2d3148 !important;
    color: #94a3b8 !important;
    border-radius: 8px !important;
}

/* ── Markdown ── */
.gr-markdown {
    color: #cbd5e1 !important;
}
.gr-markdown h2 {
    color: #e2e8f0 !important;
    border-bottom: 1px solid #2d3148 !important;
    padding-bottom: 0.5rem !important;
}
.gr-markdown code {
    background: #1e2130 !important;
    color: #a5b4fc !important;
    border-radius: 4px !important;
    padding: 1px 5px !important;
}
.gr-markdown pre {
    background: #1e2130 !important;
    border: 1px solid #2d3148 !important;
    border-radius: 8px !important;
    padding: 1rem !important;
}

/* ── Dataframe / Table ── */
.gr-dataframe table {
    border-collapse: collapse !important;
    width: 100% !important;
}
.gr-dataframe th {
    background: #1e2130 !important;
    color: #6366f1 !important;
    font-weight: 700 !important;
    padding: 10px 14px !important;
    border-bottom: 2px solid #2d3148 !important;
}
.gr-dataframe td {
    background: #13161f !important;
    color: #cbd5e1 !important;
    padding: 9px 14px !important;
    border-bottom: 1px solid #1e2130 !important;
    font-size: 0.85rem !important;
}

/* ── Status box ── */
.status-box {
    background: #1a1e2e !important;
    border-left: 4px solid #6366f1 !important;
    border-radius: 8px !important;
    padding: 12px 16px !important;
}
"""


# ── Build UI ──────────────────────────────────────────────────────────────────

_THEME = gr.themes.Base(
    primary_hue="indigo",
    neutral_hue="slate",
    font=gr.themes.GoogleFont("Inter"),
)


def build_ui() -> gr.Blocks:
    with gr.Blocks(
        title="Dify2OpenAI — API Manager",
    ) as demo:

        # ── Header ──
        gr.Markdown("""
# 🚀 Dify2OpenAI — API Manager
Manage your Dify app proxies as **OpenAI-compatible endpoints**.
Each endpoint you create gets its own `/apis/{id}/v1/chat/completions` URL.
        """)

        with gr.Tabs():

            # ════════════════════════════════════════
            #  Tab 1 — Create New API
            # ════════════════════════════════════════
            with gr.TabItem("➕  Create API"):
                gr.Markdown("### Create a new OpenAI-compatible proxy for a Dify app")

                with gr.Row():
                    with gr.Column(scale=1):
                        c_name = gr.Textbox(
                            label="API Name",
                            placeholder="e.g. My Customer Support Bot",
                            info="A human-readable name. Used to generate the URL slug.",
                        )
                        c_base_url = gr.Textbox(
                            label="Dify Base URL",
                            placeholder="https://api.dify.ai",
                            value="https://api.dify.ai",
                            info="The base URL of your Dify deployment (no trailing slash).",
                        )
                        c_api_key = gr.Textbox(
                            label="Dify App API Key",
                            placeholder="app-xxxxxxxxxxxxxxxxxxxxxxxx",
                            type="password",
                            info="The API key for your specific Dify app.",
                        )
                        c_inputs = gr.Textbox(
                            label="Default Inputs (JSON)",
                            placeholder='{\n  "language": "en",\n  "custom_field": "value"\n}',
                            lines=6,
                            info="Optional JSON object with default input fields sent to Dify on every request.",
                        )
                        c_btn = gr.Button("🚀 Create API", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        gr.Markdown("""
#### 📖 How to use

1. Enter a **name** for your API (e.g. _HR Assistant_).
2. Enter the **Dify base URL** (default: `https://api.dify.ai` for Dify Cloud).
3. Paste your **Dify App API key** — find it in your Dify app settings.
4. _(Optional)_ Add **default inputs** as a JSON object — these are extra fields sent to Dify's `inputs` field on every request.
5. Click **Create API**.

Your endpoint will be available at:
```
POST /apis/{slug}/v1/chat/completions
```

**Compatible with any OpenAI client** — just change the `base_url`.
                        """)
                        c_result = gr.Markdown(
                            value="*Results will appear here after creation.*",
                            elem_classes=["status-box"],
                        )

                c_btn.click(
                    fn=create_api_action,
                    inputs=[c_name, c_base_url, c_api_key, c_inputs],
                    outputs=[c_result, c_name, c_base_url, c_api_key, c_inputs],
                )

            # ════════════════════════════════════════
            #  Tab 2 — Manage APIs
            # ════════════════════════════════════════
            with gr.TabItem("📋  Manage APIs"):
                gr.Markdown("### All registered API proxies")

                with gr.Row():
                    m_refresh_btn = gr.Button("🔄 Refresh", variant="secondary")
                    m_count = gr.Markdown("**Loading…**")

                m_table = gr.Dataframe(
                    headers=["ID (slug)", "Name", "Base URL", "API Key (masked)", "Default Inputs", "Created At"],
                    datatype=["str", "str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                )

                gr.Markdown("---")
                gr.Markdown("#### 🔍 API Detail")
                with gr.Row():
                    m_detail_id = gr.Textbox(
                        label="API ID",
                        placeholder="Enter the ID/slug to view details",
                        scale=3,
                    )
                    m_detail_btn = gr.Button("View Detail", variant="secondary", scale=1)
                m_detail_out = gr.Markdown(value="")

                gr.Markdown("---")
                gr.Markdown("#### 🗑️ Delete API")
                with gr.Row():
                    m_delete_id = gr.Textbox(
                        label="API ID to Delete",
                        placeholder="Enter the ID/slug to delete",
                        scale=3,
                    )
                    m_delete_btn = gr.Button("🗑️ Delete", variant="stop", scale=1)
                m_delete_out = gr.Markdown(value="")

                # Wire up
                def _load():
                    t, c = refresh_list()
                    return t, c

                demo.load(fn=_load, outputs=[m_table, m_count])
                m_refresh_btn.click(fn=refresh_list, outputs=[m_table, m_count])
                m_detail_btn.click(fn=get_detail, inputs=[m_detail_id], outputs=[m_detail_out])
                m_delete_btn.click(
                    fn=delete_api_action,
                    inputs=[m_delete_id],
                    outputs=[m_delete_out, m_table, m_count],
                )

            # ════════════════════════════════════════
            #  Tab 3 — Edit API
            # ════════════════════════════════════════
            with gr.TabItem("✏️  Edit API"):
                gr.Markdown("### Update an existing API configuration")

                with gr.Row():
                    e_load_id = gr.Textbox(
                        label="API ID to Edit",
                        placeholder="Enter ID/slug then click Load",
                        scale=3,
                    )
                    e_load_btn = gr.Button("Load", variant="secondary", scale=1)

                e_load_status = gr.Markdown("")

                with gr.Row():
                    with gr.Column():
                        e_name = gr.Textbox(label="Name", placeholder="Display name")
                        e_base_url = gr.Textbox(label="Dify Base URL", placeholder="https://api.dify.ai")
                        e_api_key = gr.Textbox(label="API Key", placeholder="app-...", type="password")
                        e_inputs = gr.Textbox(
                            label="Default Inputs (JSON)",
                            placeholder='{"key": "value"}',
                            lines=5,
                        )
                        e_save_btn = gr.Button("💾 Save Changes", variant="primary")
                        e_save_out = gr.Markdown("")

                e_load_btn.click(
                    fn=load_for_edit,
                    inputs=[e_load_id],
                    outputs=[e_name, e_base_url, e_api_key, e_inputs, e_load_status],
                )
                e_save_btn.click(
                    fn=save_edit_action,
                    inputs=[e_load_id, e_name, e_base_url, e_api_key, e_inputs],
                    outputs=[e_save_out],
                )

    return demo
