"""Transparent baseline analysis. Not a trained AI sentiment model."""
import re
from collections import Counter

POSITIVE = set('good great excellent love amazing helpful happy fantastic fast recommend'.split())
NEGATIVE = set('bad terrible hate broken slow awful disappointed outage expensive poor failure'.split())
STOP = set('the a an and or to of is it this that for in on my we you i with was are have but our your'.split())


def sentiment(text):
    words = re.findall(r"\w+", text.lower())
    score = 0
    for index, word in enumerate(words):
        value = int(word in POSITIVE) - int(word in NEGATIVE)
        if any(w in {'not', 'never', 'no'} for w in words[max(0, index-3):index]):
            value *= -1
        score += value
    return 'positive' if score > 0 else 'negative' if score < 0 else 'neutral'


def summarize(posts):
    counts = Counter(p['sentiment'] for p in posts)
    topics = Counter()
    for post in posts:
        topics.update(set(w for w in re.findall(r'\w+', post['text'].lower()) if len(w) > 3 and w not in STOP))
    return {'total': len(posts), 'sentiment': {k: counts[k] for k in ('positive', 'neutral', 'negative')},
            'topics': [{'name': k, 'count': v} for k, v in topics.most_common(8)],
            'method': 'English keyword baseline; not a trained AI model. Review original posts.'}
