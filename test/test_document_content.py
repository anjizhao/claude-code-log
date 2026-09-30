"""Tests for document content item handling (e.g. PDF reads)."""

import base64
import json
import tempfile
from pathlib import Path

from claude_code_log.converter import load_transcript
from claude_code_log.factories.transcript_factory import create_content_item
from claude_code_log.html.renderer import generate_html
from claude_code_log.models import TextContent


class TestSummarizeDocument:
    """Unit tests for _summarize_document via create_content_item."""

    def test_pdf_document_produces_text_summary(self):
        item = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.b64encode(b"x" * 1000).decode(),
            },
        }
        result = create_content_item(item)
        assert isinstance(result, TextContent)
        assert "application/pdf" in result.text
        assert "document" in result.text.lower()

    def test_document_summary_shows_size_in_kb(self):
        data = base64.b64encode(b"x" * 50_000).decode()
        item = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        }
        result = create_content_item(item)
        assert isinstance(result, TextContent)
        assert "KB" in result.text

    def test_document_summary_shows_size_in_mb(self):
        data = base64.b64encode(b"x" * 2_000_000).decode()
        item = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": data},
        }
        result = create_content_item(item)
        assert isinstance(result, TextContent)
        assert "MB" in result.text

    def test_document_summary_shows_size_in_bytes(self):
        data = base64.b64encode(b"x" * 100).decode()
        item = {
            "type": "document",
            "source": {"type": "base64", "media_type": "text/plain", "data": data},
        }
        result = create_content_item(item)
        assert isinstance(result, TextContent)
        assert "bytes" in result.text
        assert "text/plain" in result.text

    def test_document_with_missing_source(self):
        item = {"type": "document"}
        result = create_content_item(item)
        assert isinstance(result, TextContent)
        assert "unknown" in result.text

    def test_document_does_not_contain_base64_data(self):
        raw_data = base64.b64encode(b"x" * 1000).decode()
        item = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": raw_data},
        }
        result = create_content_item(item)
        assert isinstance(result, TextContent)
        assert raw_data not in result.text

    def test_document_bypasses_type_filter(self):
        """Document handling runs before the type filter check."""
        item = {
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": "abc="},
        }
        result = create_content_item(item, type_filter=("text",))
        assert isinstance(result, TextContent)
        assert "application/pdf" in result.text


class TestDocumentInTranscript:
    """Integration test: document content item in a full JSONL transcript."""

    def test_document_message_renders_summary_not_base64(self):
        raw_data = base64.b64encode(b"x" * 5000).decode()
        user_msg = {
            "type": "user",
            "timestamp": "2026-09-23T20:29:05.023Z",
            "parentUuid": None,
            "isSidechain": False,
            "userType": "external",
            "cwd": "/tmp",
            "sessionId": "test-session",
            "version": "2.1.0",
            "uuid": "msg-001",
            "isMeta": True,
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": raw_data,
                        },
                    }
                ],
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps(user_msg) + "\n")
            f.flush()
            test_file = Path(f.name)

        try:
            messages = load_transcript(test_file)
            html = generate_html(messages, "Test")
            assert raw_data not in html
            assert "application/pdf" in html
        finally:
            test_file.unlink()
