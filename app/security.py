import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from threading import Lock


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ':' + digest


def verify_password(password, stored):
    salt, expected = stored.split(':')
    actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(actual, expected)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class RateLimiter:
    def __init__(self):
        self.entries = defaultdict(deque)
        self.lock = Lock()

    def allow(self, key, limit=10, window=300):
        with self.lock:
            current = time.monotonic()
            # Bound memory across unauthenticated clients.
            if len(self.entries) > 10000:
                self.entries = defaultdict(deque, {k: v for k, v in self.entries.items() if v and v[-1] > current-window})
            queue = self.entries[key]
            while queue and queue[0] <= current-window:
                queue.popleft()
            if len(queue) >= limit:
                return False
            queue.append(current)
            return True
