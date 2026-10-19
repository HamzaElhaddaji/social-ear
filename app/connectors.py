"""Explicit, user-triggered collection from a fixed public Bluesky endpoint."""
import time
import httpx


def bluesky(query):
    for attempt in range(3):
        response = httpx.get('https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts',
                             params={'q': query, 'limit': 100, 'sort': 'latest'},
                             timeout=20, follow_redirects=False)
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
        if response.status_code != 200:
            raise ValueError(f'Bluesky returned HTTP {response.status_code}. Public search availability depends on the provider; CSV imports remain available.')
        return [{'text': p.get('record', {}).get('text', ''), 'source': 'Bluesky',
                 'published_at': p.get('record', {}).get('createdAt', '')} for p in response.json().get('posts', [])]
    return []
