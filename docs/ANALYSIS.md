# Analysis design

## Sentiment

The default backend uses [VADER](https://github.com/cjhutto/vaderSentiment), an English lexicon/rule system, with small explicit product-support rules. A compound score at least 0.05 is positive; at most -0.05 is negative. Other values are neutral. Product issue phrases and lexicon additions are versioned as `vader-3.3.2-domain-v1`. Optional [local multilingual inference](MULTILINGUAL.md) replaces sentiment labels with a pinned transformer prediction. Scores are not calibrated probabilities.

Language detection is deterministic via a fixed seed, but may be wrong for short, mixed-language or informal text. Automatically detected non-English records are unclassified. Text with fewer than four words has undetermined language and may receive an English lexicon estimate. Human review can override any sentiment. Reanalysis preserves reviewed labels and all assignments/notes.

Aspects use matching clauses from a small product vocabulary. Intent uses question punctuation and negative sentiment. Both are heuristic and must not be described as trained aspect/intent models.

## Topics and research

Text is converted to sparse features with [scikit-learn TF-IDF](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction). K-means groups filtered posts into up to five clusters; top-weight terms label each cluster. This is statistical topic discovery, not semantic understanding. English stop-word removal may be unsuitable for other languages.

The research assistant ranks posts by TF-IDF cosine similarity to a question and returns up to five positive-relevance matches. Default extractive mode computes their sentiment counts. Optional [local generative mode](GENERATIVE_RESEARCH.md) sends only bounded retrieved excerpts to a configured local Ollama service and validates claim structure/citation IDs. No cloud AI service is involved. The relevance threshold is a retrieval heuristic, not a factual-confidence score.

## Monitoring

Monitors check case-insensitive substring matches in the rolling previous 24 hours, optionally restricted by sentiment. Dates are normalized to UTC at import. Records without a published time use ingestion time. Future-dated records do not trigger current alerts. Identical matching post sets do not generate another alert for the same monitor. This is a count threshold, not a trained anomaly or crisis prediction model.

## Validation boundaries

Regression tests cover known product complaint phrases, baseline non-English abstention, report totals, real-record citations and preservation of human review. Optional live-model tests cover basic multilingual predictions. These tests do not establish population accuracy. A labeled, representative, held-out dataset is required before quoting accuracy. Citation-ID validation does not establish the truth of generated claims.
