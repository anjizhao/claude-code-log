"""Tests for --sessions-since filtering."""

import json
import os
import time
from pathlib import Path


from claude_code_log.converter import load_directory_transcripts


def _write_jsonl(path: Path, session_id: str, timestamp: str) -> None:
    """Write a minimal JSONL file with one user message."""
    entry = {
        "type": "user",
        "parentUuid": None,
        "isSidechain": False,
        "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        "timestamp": timestamp,
        "uuid": session_id,
        "sessionId": session_id,
        "userType": "human",
        "cwd": "/tmp",
        "version": "2.0.0",
    }
    path.write_text(json.dumps(entry) + "\n")


class TestSessionsSince:
    def test_skips_old_sessions(self, tmp_path: Path) -> None:
        _write_jsonl(
            tmp_path / "old-session.jsonl", "old-session", "2025-01-01T00:00:00Z"
        )
        _write_jsonl(
            tmp_path / "new-session.jsonl", "new-session", "2026-08-01T00:00:00Z"
        )
        # Set mtime of old file to the past
        old_mtime = time.time() - 365 * 86400
        os.utime(tmp_path / "old-session.jsonl", (old_mtime, old_mtime))

        cutoff = time.time() - 30 * 86400  # 30 days ago
        messages = load_directory_transcripts(tmp_path, sessions_since_cutoff=cutoff)

        session_ids = {
            getattr(m, "sessionId", None)
            for m in messages
            if getattr(m, "sessionId", None)
        }
        assert "new-session" in session_ids
        assert "old-session" not in session_ids

    def test_no_cutoff_loads_all(self, tmp_path: Path) -> None:
        _write_jsonl(tmp_path / "a.jsonl", "a", "2025-01-01T00:00:00Z")
        _write_jsonl(tmp_path / "b.jsonl", "b", "2026-08-01T00:00:00Z")
        old_mtime = time.time() - 365 * 86400
        os.utime(tmp_path / "a.jsonl", (old_mtime, old_mtime))

        messages = load_directory_transcripts(tmp_path)

        session_ids = {
            getattr(m, "sessionId", None)
            for m in messages
            if getattr(m, "sessionId", None)
        }
        assert "a" in session_ids
        assert "b" in session_ids

    def test_agent_files_still_excluded(self, tmp_path: Path) -> None:
        _write_jsonl(tmp_path / "agent-abc.jsonl", "agent", "2026-08-01T00:00:00Z")
        _write_jsonl(tmp_path / "real.jsonl", "real", "2026-08-01T00:00:00Z")

        messages = load_directory_transcripts(tmp_path, sessions_since_cutoff=0.0)

        session_ids = {
            getattr(m, "sessionId", None)
            for m in messages
            if getattr(m, "sessionId", None)
        }
        assert "real" in session_ids
        assert "agent" not in session_ids
