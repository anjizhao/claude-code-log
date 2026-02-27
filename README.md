# Claude Code Log

A CLI tool that converts Claude Code transcript JSONL files into readable HTML pages.

> Forked from [daaain/claude-code-log](https://github.com/daaain/claude-code-log). See that repo for demos, feature overview, and the full changelog.

## Installation

```bash
pip install claude-code-log
```

Or run directly with uvx:

```bash
uvx claude-code-log@latest
```

Or install from source:

```bash
git clone https://github.com/anjizhao/claude-code-log.git
cd claude-code-log
uv sync
uv run claude-code-log
```

### Running from a local clone

If you have a local clone, you can run it from anywhere without installing:

```bash
uv run --directory /path/to/claude-code-log claude-code-log [options]
```

## Usage

```bash
# Process all projects (default)
claude-code-log

# Process all projects and open in browser
claude-code-log --open-browser

# Process a single file
claude-code-log path/to/transcript.jsonl

# Process a specific project directory
claude-code-log /path/to/project/directory
```

## CLI Options

| Option | Description |
|---|---|
| `INPUT_PATH` | Path to a JSONL file, directory, or project path. Defaults to `~/.claude/projects/` with `--all-projects`. |
| `-o`, `--output PATH` | Custom output file path. |
| `--open-browser` | Open the generated HTML in the default browser. |
| `--from-date TEXT` | Filter messages from this date. Supports natural language (e.g. `"yesterday"`, `"2 hours ago"`, `"2025-06-08"`). |
| `--to-date TEXT` | Filter messages up to this date. Same format as `--from-date`. |
| `--all-projects` | Process all projects in `~/.claude/projects/`. This is the default when no input path is given. |
| `--no-individual-sessions` | Skip generating individual session HTML files. |
| `--no-cache` | Disable caching and force reprocessing of all files. |
| `--clear-cache` | Clear all cache data before processing. |
| `--clear-output` / `--clear-html` | Clear generated HTML files and force regeneration. |
| `--projects-dir PATH` | Custom projects directory (default: `~/.claude/projects/`). |
| `--page-size INT` | Max messages per page for combined transcript (default: 2000). Sessions are never split across pages. |
| `--show-stats` | Show token usage statistics in generated output (hidden by default). |
| `--debug` | Show full traceback on errors. |

## Output Files

When processing all projects (the default), the tool generates HTML files alongside the source JSONL files:

```
~/.claude/projects/
├── index.html                        # Top-level index with project cards
├── -Users-you-code-project-a/
│   ├── combined_transcripts.html     # All sessions for this project
│   ├── session-{id}.html            # Individual session pages
│   └── *.jsonl                       # Source transcript files
├── -Users-you-code-project-b/
│   ├── combined_transcripts.html
│   ├── session-{id}.html
│   └── *.jsonl
└── ...
```

When processing a single file or directory, output goes to the same location as the input (or use `-o` to specify).

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and architecture docs.
