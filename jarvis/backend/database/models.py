"""SQLite table definitions as SQL string constants."""

CREATE_CONVERSATIONS = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    timestamp   DATETIME DEFAULT (datetime('now'))
);
"""

CREATE_TASKS = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT,
    due_date    TEXT,
    priority    TEXT    DEFAULT 'medium',
    status      TEXT    DEFAULT 'pending',
    created_at  DATETIME DEFAULT (datetime('now')),
    updated_at  DATETIME DEFAULT (datetime('now'))
);
"""

CREATE_NOTES = """
CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    content     TEXT,
    tags        TEXT,
    created_at  DATETIME DEFAULT (datetime('now')),
    updated_at  DATETIME DEFAULT (datetime('now'))
);
"""

CREATE_REMINDERS = """
CREATE TABLE IF NOT EXISTS reminders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    message      TEXT,
    remind_at    TEXT    NOT NULL,
    is_triggered INTEGER DEFAULT 0,
    created_at   DATETIME DEFAULT (datetime('now'))
);
"""

CREATE_USER_PREFERENCES = """
CREATE TABLE IF NOT EXISTS user_preferences (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    key        TEXT    NOT NULL UNIQUE,
    value      TEXT,
    updated_at DATETIME DEFAULT (datetime('now'))
);
"""

CREATE_LEETCODE = """
CREATE TABLE IF NOT EXISTS leetcode (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_id INTEGER NOT NULL UNIQUE,
    title      TEXT    NOT NULL,
    difficulty TEXT,
    status     TEXT    DEFAULT 'unsolved',
    notes      TEXT,
    solved_at  DATETIME
);
"""

# All table creation statements in dependency order
ALL_TABLES: list[str] = [
    CREATE_CONVERSATIONS,
    CREATE_TASKS,
    CREATE_NOTES,
    CREATE_REMINDERS,
    CREATE_USER_PREFERENCES,
    CREATE_LEETCODE,
]
