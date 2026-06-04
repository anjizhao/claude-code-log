# Claude Code Log

A CLI tool that converts Claude Code transcript JSONL files into readable HTML pages.

> Forked from [daaain/claude-code-log](https://github.com/daaain/claude-code-log). See that repo for demos, feature overview, and the full changelog.

## Installation

This fork is not published to PyPI. To get the features and fixes added here, clone the repo and run it from your local clone with `uv run --directory`:

```bash
git clone https://github.com/anjizhao/claude-code-log.git
uv run --directory /path/to/claude-code-log claude-code-log [options]
```

A shell alias makes this convenient, e.g. `alias ccl='uv run --directory /path/to/claude-code-log claude-code-log'`.

### Upstream package (does not include this fork's changes)

The commands below install the upstream `claude-code-log` package from PyPI. They will not include any of the features or fixes added in this fork.

```bash
pip install claude-code-log
```

Or run directly with uvx:

```bash
uvx claude-code-log@latest
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

## Caching & Regeneration

Normal runs are fully incremental: transcript file changes are detected automatically and only affected sessions are re-parsed and regenerated. No special flags needed.

The `--regenerate`, `--clear-cache`, and `--clear-output` flags are for when the *rendering code* changes (templates, CSS) but transcripts haven't. See the CLI options table below for details.

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
| `--regenerate N` | Force HTML regeneration for sessions active within the last N seconds (e.g. `86400` = 1 day). Use after template/CSS changes. |
| `--clear-cache` | Clear all cache data and regenerate. |
| `--clear-output` / `--clear-html` | Clear generated HTML files and regenerate. |
| `--projects-since TEXT` | Only refresh projects with activity since this date (e.g. `"7d"`, `"1 week ago"`). Older projects still appear in the index using cached data. Only applies when processing all projects. |
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
│   ├── index.html                   # Project session index
│   ├── session-{id}.html            # Individual session pages
│   └── *.jsonl                       # Source transcript files
├── -Users-you-code-project-b/
│   ├── index.html
│   ├── session-{id}.html
│   └── *.jsonl
└── ...
```

When processing a single file or directory, output goes to the same location as the input (or use `-o` to specify).

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and architecture docs.
