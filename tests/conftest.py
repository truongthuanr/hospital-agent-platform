import os

os.environ.setdefault("SESSION_HASH_KEY", "test-only-session-hash-key-at-least-32-bytes")
os.environ.setdefault("DEMO_STAFF_PASSWORD", "test-only-password")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

