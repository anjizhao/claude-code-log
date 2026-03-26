# Managing Archived Sessions

When you run `claude-code-log`, you may see output like:

```sh
project-name: cached, 3 archived (0.0s)
```

This indicates that 3 sessions exist in the cache whose source JSONL files have been deleted.

## What Are Archived Sessions?

Archived sessions are sessions preserved in the SQLite cache (`~/.claude/projects/claude-code-log-cache.db`) even after their source JSONL files have been deleted. This happens when:

1. Claude Code automatically deletes old JSONL files based on the `cleanupPeriodDays` setting
2. You manually delete JSONL files from `~/.claude/projects/*/`
3. You archive sessions using the TUI (`a` key)

The cache stores the complete message data, so full restoration is possible.

## Preventing Automatic Deletion

Claude Code automatically deletes session logs after 30 days by default. To change this, add `cleanupPeriodDays` to your `~/.claude/settings.json`:

```json
{
  "cleanupPeriodDays": 99999
}
```

This effectively disables automatic cleanup (274 years). You can also set it to a specific number of days.

See Claude Code's [settings documentation](https://docs.anthropic.com/en/docs/claude-code/settings) for more details.

## Using the TUI to Manage Archived Sessions

The easiest way to browse and restore archived sessions is through the interactive TUI.

### Launch the TUI

```bash
claude-code-log --tui
```

### Viewing Archived Sessions

Archived sessions appear inline with current sessions, marked with an `[ARCHIVED]` prefix:

```text
┌─ Claude Code Log ─────────────────────────────────────────────────┐
│ Project: my-project (3 archived)                                  │
│ Sessions: 5 │ Messages: 456 │ Tokens: 45,230                      │
├──────────┬───────────────────────────────────────┬─────────┬──────┤
│ Session  │ Title                                 │ Start   │ Msgs │
├──────────┼───────────────────────────────────────┼─────────┼──────┤
│ xyz789   │ Current session                       │ 01-20   │ 32   │
│ abc123   │ [ARCHIVED] Fix authentication bug     │ 12-01   │ 45   │
│ def456   │ [ARCHIVED] Add user settings page     │ 11-28   │ 123  │
└──────────┴───────────────────────────────────────┴─────────┴──────┘
 [a] Archive  [r] Restore  [h] HTML  [v] View  [c] Resume  [q] Quit
```

### Archive and Restore Keys

- `a` - **Archive Session**: Deletes the JSONL file but keeps the session in cache
- `r` - **Restore JSONL**: Recreates the JSONL file from cached data

### Restore a Session

1. Navigate to the archived session (marked with `[ARCHIVED]`)
2. Press `r` to restore the session to a JSONL file
3. The session will be restored to `~/.claude/projects/{project}/{session-id}.jsonl`
4. The `[ARCHIVED]` prefix will be removed after the session list refreshes

### View Archived Sessions

You can view archived sessions as HTML or Markdown without restoring them:

- `h` - Open HTML in browser
- `m` - Open Markdown in browser
- `v` - View Markdown in embedded viewer

## Permanently Deleting Sessions

To fully remove a session (both the JSONL file and all cached data), you need to delete from three places: the JSONL file on disk, and the `messages`, `sessions`, and `cached_files` tables in the cache DB.

### 1. Find the session

```sql
sqlite3 ~/.claude/projects/claude-code-log-cache.db

-- Find sessions for a project
SELECT s.session_id, s.first_timestamp, s.message_count
FROM sessions s
JOIN projects p ON s.project_id = p.id
WHERE p.project_path LIKE '%your-project-name%';
```

### 2. Find the cached_files entry

```sql
SELECT DISTINCT cf.id, cf.file_path
FROM cached_files cf
JOIN messages m ON m.file_id = cf.id
WHERE m.session_id = 'your-session-id';
```

### 3. Delete everything

```bash
# Delete the JSONL file (skip if already deleted)
rm ~/.claude/projects/{project-name}/{session-id}.jsonl

# Delete from the cache DB (replace SESSION_ID and FILE_ID with actual values)
sqlite3 ~/.claude/projects/claude-code-log-cache.db \
  "DELETE FROM messages WHERE session_id = 'SESSION_ID';
   DELETE FROM sessions WHERE session_id = 'SESSION_ID';
   DELETE FROM cached_files WHERE id = FILE_ID;"
```

Also delete the generated HTML file if one exists:

```bash
rm ~/.claude/projects/{project-name}/session-{session-id}.html
```

## Limitations

- **Message order**: Messages are ordered by timestamp, which may differ slightly from original file order for same-timestamp entries
- **Whitespace**: Original JSON formatting is not preserved (semantically identical)

## Manual SQL Approach

For advanced users, you can also query the cache database directly:

```bash
sqlite3 ~/.claude/projects/claude-code-log-cache.db
```

```sql
-- List all sessions
SELECT p.project_path, s.session_id, s.first_timestamp, s.message_count
FROM sessions s
JOIN projects p ON s.project_id = p.id
ORDER BY s.first_timestamp;

-- Export a session's messages
SELECT content FROM messages WHERE session_id = 'your-session-id' ORDER BY timestamp;
```
