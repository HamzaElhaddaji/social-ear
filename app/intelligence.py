"""Local analysis with explicit provenance and evidence-backed retrieval."""
import re
from collections import Counter
from functools import lru_cache
from langdetect import detect, DetectorFactory, LangDetectException
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

DetectorFactory.seed = 0
LABELS = ('positive', 'neutral', 'negative')


@lru_cache(maxsize=1)
def analyzer():
    model = SentimentIntensityAnalyzer()
    model.lexicon.update({'broken': -2.5, 'outage': -2.5, 'expensive': -1.5, 'crashing': -2.5, 'slow': -1.5})
    return model


def sentiment_score(text):
    value = analyzer().polarity_scores(text)['compound']
    # Product-support phrases are often missed by the general social lexicon.
    issues = ('not responding', 'cannot log in', "can't log in", 'not working', "doesn't work", 'keeps crashing')
    return max(-1.0, value - .6 * sum(phrase in text.lower() for phrase in issues))


def analyze(text):
    try:
        language = detect(text) if len(text.split()) >= 4 else 'und'
    except LangDetectException:
        language = 'und'
    score = sentiment_score(text)
    label = 'positive' if score >= .05 else 'negative' if score <= -.05 else 'neutral'
    # VADER is English. Do not present unsupported languages as neutral predictions.
    if language not in ('en', 'und'):
        label, score = 'unclassified', None
    intent = 'question' if '?' in text else 'complaint' if label == 'negative' else 'feedback'
    aspects = {}
    for key, terms in {'pricing': ('price', 'pricing', 'expensive', 'cheap'), 'support': ('support', 'service'), 'performance': ('slow', 'fast', 'crash', 'broken', 'outage'), 'usability': ('design', 'interface', 'dashboard', 'easy')}.items():
        clauses = [c for c in re.split(r'[.!?;]|\bbut\b', text.lower()) if any(t in c for t in terms)]
        if clauses:
            value = sentiment_score(' '.join(clauses))
            aspects[key] = ('positive' if value >= .05 else 'negative' if value <= -.05 else 'neutral') if label != 'unclassified' else 'unclassified'
    return {'sentiment': label, 'score': score, 'language': language, 'intent': intent, 'aspects': aspects,
            'model': 'vader-3.3.2-domain-v1', 'reviewed': False}


def overview(posts):
    counts = Counter(p['sentiment'] for p in posts)
    days = {}
    sources = {}
    for post in posts:
        day = post.get('published_at', '')[:10] or post.get('created_at', '')[:10]
        bucket = days.setdefault(day, {'date': day, 'total': 0, 'negative': 0})
        bucket['total'] += 1
        bucket['negative'] += post['sentiment'] == 'negative'
        source = sources.setdefault(post.get('source', 'Import'), {'name': post.get('source', 'Import'), 'total': 0, 'negative': 0})
        source['total'] += 1
        source['negative'] += post['sentiment'] == 'negative'
    topics = []
    if posts:
        try:
            vectorizer = TfidfVectorizer(stop_words='english', max_features=2000, ngram_range=(1, 2))
            matrix = vectorizer.fit_transform([p['text'] for p in posts])
            terms = vectorizer.get_feature_names_out()
            n = min(5, len(posts), max(1, len(set(p['text'] for p in posts))))
            model = KMeans(n_clusters=n, random_state=42, n_init=5).fit(matrix)
            for index, center in enumerate(model.cluster_centers_):
                members = [posts[i]['id'] for i, value in enumerate(model.labels_) if value == index]
                if members:
                    topics.append({'name': ' / '.join(terms[i] for i in center.argsort()[-3:][::-1]), 'count': len(members), 'evidence': members[:5]})
        except ValueError:
            pass
    return {'total': len(posts), 'sentiment': {k: counts[k] for k in (*LABELS, 'unclassified')},
            'topics': sorted(topics, key=lambda t: -t['count']), 'timeline': sorted(days.values(), key=lambda x: x['date']),
            'sources': sorted(sources.values(), key=lambda x: -x['total']),
            'method': 'VADER English sentiment · TF-IDF/K-means topic discovery · review estimates against original posts'}


def research(question, posts):
    if not posts:
        return {'answer': 'No matching conversations are available in this workspace.', 'citations': [], 'method': 'extractive'}
    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        matrix = vectorizer.fit_transform([p['text'] for p in posts] + [question])
        scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
        indices = [int(i) for i in scores.argsort()[::-1][:5] if scores[i] > .03]
    except ValueError:
        indices = []
    selected = [posts[i] for i in indices]
    if not selected:
        return {'answer': 'I could not find evidence relevant to that question. Try a specific product, feature, or complaint.', 'citations': [], 'method': 'extractive'}
    counts = Counter(p['sentiment'] for p in selected)
    return {'answer': f'Found {len(selected)} relevant conversations: {counts["positive"]} positive, {counts["negative"]} negative, {counts["neutral"]} neutral, and {counts["unclassified"]} unclassified. The evidence below is ranked by textual relevance, not representativeness.',
            'citations': [{'id': p['id'], 'text': p['text'], 'source': p['source']} for p in selected], 'method': 'local TF-IDF extractive research; no generated claims'}
