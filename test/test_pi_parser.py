"""Tests for Pi transcript parser."""

from pathlib import Path

import pytest

from claude_code_log.pi_parser import (
    _transform_content_items,
    _transform_usage,
    is_pi_transcript,
    parse_pi_transcript,
)
from claude_code_log.parser import extract_session_id
from claude_code_log.converter import load_transcript
from claude_code_log.models import (
    AssistantTranscriptEntry,
    CustomTitleTranscriptEntry,
    SystemTranscriptEntry,
    UserTranscriptEntry,
)

PI_TEST_DATA = Path(__file__).parent / "test_data" / "pi"


class TestExtractSessionId:
    def test_pi_filename(self):
        path = Path("2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl")
        assert extract_session_id(path) == "aaaa1111-2222-3333-4444-555566667777"

    def test_claude_code_filename(self):
        path = Path("29ccd257-68b1-427f-ae5f-6524b7cb6f20.jsonl")
        assert extract_session_id(path) == "29ccd257-68b1-427f-ae5f-6524b7cb6f20"

    def test_splits_at_last_underscore(self):
        path = Path("2026-10-06T15-00-00-000Z_abc123.jsonl")
        assert extract_session_id(path) == "abc123"


class TestIsPiTranscript:
    def test_pi_file(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        assert is_pi_transcript(pi_file)

    def test_claude_code_file(self):
        cc_file = Path(__file__).parent / "test_data" / "representative_messages.jsonl"
        assert not is_pi_transcript(cc_file)

    def test_nonexistent_file(self):
        assert not is_pi_transcript(Path("/nonexistent/file.jsonl"))


class TestTransformContentItems:
    def test_tool_call_to_tool_use(self):
        items = [{"type": "toolCall", "id": "t1", "name": "bash", "arguments": {"command": "ls"}}]
        result = _transform_content_items(items)
        assert result == [{"type": "tool_use", "id": "t1", "name": "bash", "input": {"command": "ls"}}]

    def test_thinking_signature_rename(self):
        items = [{"type": "thinking", "thinking": "hmm", "thinkingSignature": "sig123"}]
        result = _transform_content_items(items)
        assert result == [{"type": "thinking", "thinking": "hmm", "signature": "sig123"}]

    def test_text_passthrough(self):
        items = [{"type": "text", "text": "hello"}]
        result = _transform_content_items(items)
        assert result == [{"type": "text", "text": "hello"}]

    def test_mixed_content(self):
        items = [
            {"type": "text", "text": "I'll check"},
            {"type": "toolCall", "id": "t1", "name": "read", "arguments": {"path": "a.py"}},
        ]
        result = _transform_content_items(items)
        assert len(result) == 2
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "tool_use"
        assert result[1]["input"] == {"path": "a.py"}


class TestTransformUsage:
    def test_basic_mapping(self):
        usage = {"input": 100, "output": 50, "cacheRead": 5000, "cacheWrite": 1000}
        result = _transform_usage(usage)
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["cache_read_input_tokens"] == 5000
        assert result["cache_creation_input_tokens"] == 1000

    def test_missing_fields(self):
        usage = {"input": 10}
        result = _transform_usage(usage)
        assert result["input_tokens"] == 10
        assert result["output_tokens"] is None


class TestParsePiTranscript:
    """Test full parsing of Pi JSONL files."""

    def test_basic_session(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)

        # Should have: model_change(system) + 2 user + 4 assistant + 3 tool_results(as user)
        # = 10 entries total (system prompt and thinking_level_change skipped)
        assert len(messages) > 0

        # All entries should have the correct session ID
        for msg in messages:
            if hasattr(msg, "sessionId") and msg.sessionId:
                assert msg.sessionId == "aaaa1111-2222-3333-4444-555566667777"

    def test_user_messages(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)
        user_msgs = [m for m in messages if isinstance(m, UserTranscriptEntry)]

        # 2 real user messages + 5 tool results wrapped as user entries
        assert len(user_msgs) == 7

    def test_assistant_messages(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)
        assistant_msgs = [m for m in messages if isinstance(m, AssistantTranscriptEntry)]

        assert len(assistant_msgs) == 6

    def test_assistant_has_usage(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)
        assistant_msgs = [m for m in messages if isinstance(m, AssistantTranscriptEntry)]

        first_assistant = assistant_msgs[0]
        assert first_assistant.message.usage is not None
        assert first_assistant.message.usage.input_tokens == 100
        assert first_assistant.message.usage.output_tokens == 50

    def test_tool_use_content_transformed(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)
        assistant_msgs = [m for m in messages if isinstance(m, AssistantTranscriptEntry)]

        first_assistant = assistant_msgs[0]
        content_types = [item.type for item in first_assistant.message.content]
        assert "thinking" in content_types
        assert "text" in content_types
        assert "tool_use" in content_types
        assert "toolCall" not in content_types

    def test_tool_results_have_tool_use_id(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)
        from claude_code_log.models import ToolResultContent

        for msg in messages:
            if isinstance(msg, UserTranscriptEntry):
                for item in msg.message.content:
                    if isinstance(item, ToolResultContent):
                        assert item.tool_use_id != ""

    def test_system_prompt_skipped(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)
        system_msgs = [m for m in messages if isinstance(m, SystemTranscriptEntry)]

        # Should have model_change as system, but NOT the system prompt
        for msg in system_msgs:
            assert msg.content is not None
            assert "Model changed" in msg.content

    def test_cwd_propagated(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)

        for msg in messages:
            if hasattr(msg, "cwd"):
                assert msg.cwd == "/Users/test/project"


class TestSessionWithMetadata:
    """Test parsing of Pi sessions with model changes, session_info, compaction."""

    def test_model_change_as_system_message(self):
        pi_file = PI_TEST_DATA / "2026-10-06T16-00-00-000Z_bbbb2222-3333-4444-5555-666677778888.jsonl"
        messages = parse_pi_transcript(pi_file)
        system_msgs = [m for m in messages if isinstance(m, SystemTranscriptEntry)]

        model_changes = [m for m in system_msgs if m.content and "Model changed" in m.content]
        assert len(model_changes) == 2
        assert "GLM-5.2" in model_changes[0].content
        assert "claude-opus-4-6" in model_changes[1].content

    def test_session_info_as_system_message(self):
        pi_file = PI_TEST_DATA / "2026-10-06T16-00-00-000Z_bbbb2222-3333-4444-5555-666677778888.jsonl"
        messages = parse_pi_transcript(pi_file)
        system_msgs = [m for m in messages if isinstance(m, SystemTranscriptEntry)]

        rename_msgs = [m for m in system_msgs if m.content and "Session renamed" in m.content]
        assert len(rename_msgs) == 2

    def test_latest_session_info_becomes_custom_title(self):
        pi_file = PI_TEST_DATA / "2026-10-06T16-00-00-000Z_bbbb2222-3333-4444-5555-666677778888.jsonl"
        messages = parse_pi_transcript(pi_file)
        custom_titles = [m for m in messages if isinstance(m, CustomTitleTranscriptEntry)]

        assert len(custom_titles) == 1
        assert custom_titles[0].customTitle == "fix auth bug in src/auth.py"

    def test_compaction_as_user_message(self):
        pi_file = PI_TEST_DATA / "2026-10-06T16-00-00-000Z_bbbb2222-3333-4444-5555-666677778888.jsonl"
        messages = parse_pi_transcript(pi_file)
        user_msgs = [m for m in messages if isinstance(m, UserTranscriptEntry)]

        compacted = [
            m for m in user_msgs
            if any(
                hasattr(item, "text") and "(compacted conversation)" in item.text
                for item in m.message.content
            )
        ]
        assert len(compacted) == 1

    def test_error_tool_result(self):
        pi_file = PI_TEST_DATA / "2026-10-06T16-00-00-000Z_bbbb2222-3333-4444-5555-666677778888.jsonl"
        messages = parse_pi_transcript(pi_file)
        from claude_code_log.models import ToolResultContent

        error_results = []
        for msg in messages:
            if isinstance(msg, UserTranscriptEntry):
                for item in msg.message.content:
                    if isinstance(item, ToolResultContent) and item.is_error:
                        error_results.append(item)

        assert len(error_results) == 1
        assert "No such file or directory" in error_results[0].content

    def test_usage_and_thinking_level_change_skipped(self):
        pi_file = PI_TEST_DATA / "2026-10-06T16-00-00-000Z_bbbb2222-3333-4444-5555-666677778888.jsonl"
        messages = parse_pi_transcript(pi_file)

        # No message should contain "cache_warm" or thinking level data
        for msg in messages:
            if isinstance(msg, SystemTranscriptEntry) and msg.content:
                assert "cache_warm" not in msg.content


    def test_write_tool(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)
        from claude_code_log.models import ToolUseContent

        write_calls = []
        for msg in messages:
            if isinstance(msg, AssistantTranscriptEntry):
                for item in msg.message.content:
                    if isinstance(item, ToolUseContent) and item.name == "write":
                        write_calls.append(item)
        assert len(write_calls) == 1
        assert "test_parser.py" in write_calls[0].input["path"]

    def test_ask_user_question_tool(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = parse_pi_transcript(pi_file)
        from claude_code_log.models import ToolUseContent

        ask_calls = []
        for msg in messages:
            if isinstance(msg, AssistantTranscriptEntry):
                for item in msg.message.content:
                    if isinstance(item, ToolUseContent) and item.name == "ask_user_question":
                        ask_calls.append(item)
        assert len(ask_calls) == 1
        assert "questions" in ask_calls[0].input


class TestAutoDetection:
    """Test that load_transcript auto-detects Pi format."""

    def test_pi_file_auto_detected(self):
        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = load_transcript(pi_file)
        assert len(messages) > 0

        # Verify it parsed as Pi (check session ID)
        for msg in messages:
            if hasattr(msg, "sessionId") and msg.sessionId:
                assert msg.sessionId == "aaaa1111-2222-3333-4444-555566667777"
                break

    def test_claude_code_file_still_works(self):
        cc_file = Path(__file__).parent / "test_data" / "representative_messages.jsonl"
        messages = load_transcript(cc_file)
        assert len(messages) > 0


class TestCliPiFlag:
    """Test that --pi CLI flag works."""

    def test_pi_flag_processes_directory(self, tmp_path):
        """Test --pi with a custom projects dir containing Pi sessions."""
        import shutil
        from click.testing import CliRunner
        from claude_code_log.cli import main

        # Set up a fake Pi sessions directory
        project_dir = tmp_path / "--Users-test--"
        project_dir.mkdir()
        shutil.copy(
            PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl",
            project_dir,
        )

        runner = CliRunner()
        result = runner.invoke(main, ["--projects-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "Successfully processed" in result.output

        # Check HTML files were generated
        assert (tmp_path / "index.html").exists()
        assert (project_dir / "index.html").exists()
        session_htmls = list(project_dir.glob("session-*.html"))
        assert len(session_htmls) == 1
        assert "aaaa1111" in session_htmls[0].name

    def test_pi_and_projects_dir_mutually_exclusive(self):
        from click.testing import CliRunner
        from claude_code_log.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["--pi", "--projects-dir", "/tmp/test"])
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output


class TestHtmlGeneration:
    """Test that Pi transcripts produce valid HTML through the full pipeline."""

    def test_basic_session_renders(self):
        from claude_code_log.html.renderer import generate_html

        pi_file = PI_TEST_DATA / "2026-10-06T15-00-00-000Z_aaaa1111-2222-3333-4444-555566667777.jsonl"
        messages = load_transcript(pi_file)
        html = generate_html(messages, "Pi Test Session")

        assert "<!DOCTYPE html>" in html
        assert "Help me fix the bug" in html
        assert "parser.py" in html

    def test_session_with_metadata_renders(self):
        from claude_code_log.html.renderer import generate_html

        pi_file = PI_TEST_DATA / "2026-10-06T16-00-00-000Z_bbbb2222-3333-4444-5555-666677778888.jsonl"
        messages = load_transcript(pi_file)
        html = generate_html(messages, "Pi Test Session with Metadata")

        assert "<!DOCTYPE html>" in html
        assert "Model changed" in html
        assert "Session renamed" in html
        assert "compacted conversation" in html
