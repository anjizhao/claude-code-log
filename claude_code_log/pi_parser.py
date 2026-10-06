"""Parser for Pi coding agent JSONL transcript files.

Transforms Pi transcript entries into Claude Code-shaped dicts, then feeds
them through create_transcript_entry() to produce the same TranscriptEntry
types used by the rest of the pipeline.

Pi format differences from Claude Code:
- Unified "message" type with message.role instead of separate top-level types
- Tool calls use "toolCall" with "arguments" instead of "tool_use" with "input"
- Tool results are separate messages (role: "toolResult") not embedded in user messages
- Metadata entries: session, model_change, session_info, compaction, etc.
- IDs are short hex strings, not full UUIDs
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .factories import create_transcript_entry
from .models import (
    CustomTitleTranscriptEntry,
    TranscriptEntry,
)
from .parser import extract_session_id


@dataclass
class _SessionContext:
    """State accumulated from Pi metadata entries during parsing."""

    session_id: str = ""
    cwd: str = ""
    version: str = ""
    latest_session_name: Optional[str] = None


def _transform_content_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform Pi content items to Claude Code format.

    - toolCall -> tool_use, arguments -> input
    - thinkingSignature -> signature
    """
    result = []
    for item in items:
        item_type = item.get("type")
        if item_type == "toolCall":
            result.append({
                "type": "tool_use",
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "input": item.get("arguments", {}),
            })
        elif item_type == "thinking":
            transformed = {"type": "thinking", "thinking": item.get("thinking", "")}
            sig = item.get("thinkingSignature")
            if sig:
                transformed["signature"] = sig
            result.append(transformed)
        else:
            result.append(item)
    return result


def _transform_usage(usage: dict[str, Any]) -> dict[str, Any]:
    """Transform Pi usage fields to Claude Code UsageInfo field names."""
    return {
        "input_tokens": usage.get("input"),
        "output_tokens": usage.get("output"),
        "cache_read_input_tokens": usage.get("cacheRead"),
        "cache_creation_input_tokens": usage.get("cacheWrite"),
    }


def _make_base_fields(
    pi_entry: dict[str, Any], ctx: _SessionContext
) -> dict[str, Any]:
    """Build the BaseTranscriptEntry fields from a Pi entry."""
    return {
        "uuid": pi_entry.get("id", ""),
        "parentUuid": pi_entry.get("parentId"),
        "timestamp": pi_entry.get("timestamp", ""),
        "sessionId": ctx.session_id,
        "cwd": ctx.cwd,
        "version": ctx.version,
        "isSidechain": False,
        "userType": "human",
    }


def _transform_user_message(
    pi_entry: dict[str, Any], ctx: _SessionContext
) -> dict[str, Any]:
    """Transform a Pi user message to a Claude Code user entry dict."""
    msg = pi_entry.get("message", {})
    content = msg.get("content", [])
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]

    entry = _make_base_fields(pi_entry, ctx)
    entry["type"] = "user"
    entry["message"] = {"role": "user", "content": content}
    return entry


def _transform_assistant_message(
    pi_entry: dict[str, Any], ctx: _SessionContext
) -> dict[str, Any]:
    """Transform a Pi assistant message to a Claude Code assistant entry dict."""
    msg = pi_entry.get("message", {})
    content = _transform_content_items(msg.get("content", []))

    usage = None
    if msg.get("usage"):
        usage = _transform_usage(msg["usage"])

    entry = _make_base_fields(pi_entry, ctx)
    entry["type"] = "assistant"
    entry["message"] = {
        "id": msg.get("responseId", pi_entry.get("id", "")),
        "type": "message",
        "role": "assistant",
        "model": msg.get("model", msg.get("responseModel", "")),
        "content": content,
        "stop_reason": msg.get("stopReason"),
        "usage": usage,
    }
    return entry


def _transform_tool_result(
    pi_entry: dict[str, Any], ctx: _SessionContext
) -> dict[str, Any]:
    """Transform a Pi toolResult message to a Claude Code user entry with ToolResultContent."""
    msg = pi_entry.get("message", {})

    # Extract text content from the Pi tool result
    pi_content = msg.get("content", [])
    if isinstance(pi_content, list) and pi_content:
        # Combine text items into a single string
        text_parts = []
        for item in pi_content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        result_content = "\n".join(text_parts) if text_parts else str(pi_content)
    elif isinstance(pi_content, str):
        result_content = pi_content
    else:
        result_content = str(pi_content)

    tool_result_item = {
        "type": "tool_result",
        "tool_use_id": msg.get("toolCallId", ""),
        "content": result_content,
        "is_error": msg.get("isError", False),
    }

    entry = _make_base_fields(pi_entry, ctx)
    entry["type"] = "user"
    entry["message"] = {"role": "user", "content": [tool_result_item]}
    return entry


def _transform_model_change(
    pi_entry: dict[str, Any], ctx: _SessionContext
) -> dict[str, Any]:
    """Transform a Pi model_change entry to a Claude Code system entry."""
    model_id = pi_entry.get("modelId", "unknown")

    entry = _make_base_fields(pi_entry, ctx)
    entry["type"] = "system"
    entry["level"] = "info"
    entry["content"] = f"Model changed to {model_id}"
    return entry


def _transform_session_info(
    pi_entry: dict[str, Any], ctx: _SessionContext
) -> dict[str, Any]:
    """Transform a Pi session_info entry to a Claude Code system entry."""
    name = pi_entry.get("name", "")

    entry = _make_base_fields(pi_entry, ctx)
    entry["type"] = "system"
    entry["level"] = "info"
    entry["content"] = f"Session renamed to: {name}"
    return entry


def _transform_compaction(
    pi_entry: dict[str, Any], ctx: _SessionContext
) -> dict[str, Any]:
    """Transform a Pi compaction entry to a Claude Code user entry with compacted summary."""
    summary = pi_entry.get("summary", "")
    compacted_text = f"(compacted conversation)\n\n{summary}"

    entry = _make_base_fields(pi_entry, ctx)
    entry["type"] = "user"
    entry["message"] = {
        "role": "user",
        "content": [{"type": "text", "text": compacted_text}],
    }
    return entry


def parse_pi_transcript(jsonl_path: Path, silent: bool = False) -> list[TranscriptEntry]:
    """Parse a Pi JSONL transcript file into TranscriptEntry objects.

    Transforms Pi entries into Claude Code-shaped dicts and feeds them
    through create_transcript_entry().
    """
    ctx = _SessionContext(session_id=extract_session_id(jsonl_path))
    messages: list[TranscriptEntry] = []

    try:
        f = open(jsonl_path, "r", encoding="utf-8", errors="replace")
    except FileNotFoundError:
        if not silent:
            print(f"Warning: File not found (may have been deleted): {jsonl_path}")
        return []

    with f:
        if not silent:
            print(f"Processing {jsonl_path}...")
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                pi_entry = json.loads(line)
                if not isinstance(pi_entry, dict):
                    continue

                entry_type = pi_entry.get("type")

                if entry_type == "session":
                    ctx.cwd = pi_entry.get("cwd", "")
                    ctx.version = str(pi_entry.get("version", ""))
                    continue

                if entry_type == "message":
                    role = pi_entry.get("message", {}).get("role")

                    if role == "system":
                        continue

                    if role == "user":
                        entry_dict = _transform_user_message(pi_entry, ctx)
                    elif role == "assistant":
                        entry_dict = _transform_assistant_message(pi_entry, ctx)
                    elif role == "toolResult":
                        entry_dict = _transform_tool_result(pi_entry, ctx)
                    else:
                        continue

                    messages.append(create_transcript_entry(entry_dict))
                    continue

                if entry_type == "model_change":
                    entry_dict = _transform_model_change(pi_entry, ctx)
                    messages.append(create_transcript_entry(entry_dict))
                    continue

                if entry_type == "session_info":
                    ctx.latest_session_name = pi_entry.get("name")
                    entry_dict = _transform_session_info(pi_entry, ctx)
                    messages.append(create_transcript_entry(entry_dict))
                    continue

                if entry_type == "compaction":
                    entry_dict = _transform_compaction(pi_entry, ctx)
                    messages.append(create_transcript_entry(entry_dict))
                    continue

                if entry_type in ("thinking_level_change", "usage"):
                    continue

                if not silent:
                    display_line = line[:200] + "..." if len(line) > 200 else line
                    print(
                        f"Line {line_no} of {jsonl_path} is not a recognised "
                        f"Pi entry type: {display_line}"
                    )

            except json.JSONDecodeError as e:
                if not silent:
                    print(f"Line {line_no} of {jsonl_path} | JSON decode error: {e}")
            except Exception as e:
                if not silent:
                    print(f"Line {line_no} of {jsonl_path} | Error: {e}")

    # Emit a CustomTitleTranscriptEntry if session was named
    if ctx.latest_session_name:
        messages.append(
            CustomTitleTranscriptEntry(
                type="custom-title",
                customTitle=ctx.latest_session_name,
                sessionId=ctx.session_id,
            )
        )

    return messages


def is_pi_transcript(jsonl_path: Path) -> bool:
    """Check if a JSONL file is a Pi transcript by peeking at the first line."""
    try:
        with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline().strip()
            if first_line:
                first_entry = json.loads(first_line)
                return (
                    isinstance(first_entry, dict)
                    and first_entry.get("type") == "session"
                    and "version" in first_entry
                    and "cwd" in first_entry
                )
    except (json.JSONDecodeError, OSError):
        pass
    return False



