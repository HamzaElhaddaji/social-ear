"""Explicit local demo seed. Never run against a production database."""
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from .database import database, User, Workspace, Membership
from .security import hash_password
from .service import add_posts


def seed():
    if os.environ.get('DATABASE_URL', 'sqlite:///data/platform.db') != 'sqlite:///data/platform.db':
        raise SystemExit('Demo seed is restricted to the default local SQLite database.')
    engine, factory = database()
    with factory.begin() as db:
        if db.scalar(select(User).where(User.email == 'demo@social-ear.test')):
            print('Demo account already exists. No data changed.')
            return
        user = User(email='demo@social-ear.test', name='Demo researcher', password=hash_password('Local-demo-only-2026!'))
        space = Workspace(name='Demo · Northstar Mobile')
        db.add_all([user, space]); db.flush()
        db.add(Membership(user_id=user.id, workspace_id=space.id, role='owner'))
        texts = [
            ('The support team was wonderful and solved my problem quickly.', 'Community'),
            ('The new application is terribly slow and keeps crashing.', 'Reviews'),
            ('I love the new dashboard. The design looks amazing!', 'Community'),
            ('The price is too expensive for small teams.', 'Reviews'),
            ('How can I export my monthly report?', 'Community'),
            ('Customer service was rude and unhelpful yesterday.', 'Reviews'),
            ('The update made everything faster. Great work!', 'Community'),
            ('I cannot log in and support is not responding.', 'Reviews'),
            ('The new pricing page is available today.', 'Community'),
            ('Easy interface and excellent battery performance.', 'Reviews'),
            ('Ce service est vraiment excellent et je suis très content.', 'Community'),
            ('I am frustrated by the broken notifications and bad support.', 'Reviews'),
        ]
        current = datetime.now(timezone.utc)
        add_posts(db, space.id, [{'text': text, 'source': source, 'published_at': (current-timedelta(hours=index*3)).isoformat()} for index,(text,source) in enumerate(texts)])
    engine.dispose()
    print('Synthetic local demo created. Email: demo@social-ear.test / Password: Local-demo-only-2026!')


if __name__ == '__main__':
    seed()
