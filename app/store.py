import csv
import hashlib
import io
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .analysis import sentiment


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS posts (id TEXT PRIMARY KEY, text TEXT NOT NULL, source TEXT NOT NULL, published_at TEXT NOT NULL, sentiment TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_csv(self, content):
        reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
        if not reader.fieldnames or 'text' not in reader.fieldnames:
            raise ValueError('CSV must include a text column. Optional: source, published_at.')
        records = []
        skipped = 0
        for row in reader:
            text = (row.get('text') or '').strip()
            if not text:
                skipped += 1
                continue
            if len(text) > 20000:
                raise ValueError('A post exceeds the 20,000 character limit.')
            source = (row.get('source') or 'CSV').strip()
            published = (row.get('published_at') or '').strip()
            identity = hashlib.sha256(repr((text, source, published)).encode()).hexdigest()
            records.append((identity, text, source, published, sentiment(text)))
        with self.connect() as db:
            before = db.total_changes
            db.executemany('INSERT OR IGNORE INTO posts VALUES (?,?,?,?,?)', records)
            inserted = db.total_changes - before
        return {'imported': inserted, 'duplicates': len(records)-inserted, 'empty': skipped}

    def posts(self, query='', label=''):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM posts WHERE instr(lower(text), lower(?)) > 0 AND (? = '' OR sentiment = ?) ORDER BY rowid DESC", (query, label, label)).fetchall()
        return [dict(row) for row in rows]
