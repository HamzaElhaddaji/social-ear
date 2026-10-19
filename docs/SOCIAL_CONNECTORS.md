# Social source connectors

All connectors are disabled by default and collection is triggered manually from the workspace. CSV imports continue to work without provider access. Collection runs as a background job and uses the same workspace isolation, duplicate detection, date normalization, analysis and monitor evaluation as CSV imports.

## Bluesky

Set `ENABLE_BLUESKY=1`. The query is sent to the fixed public search API. Fetches up to 100 latest matches. Availability and rate limits depend on the provider.

## Mastodon

Set `ENABLE_MASTODON=1`. The application reads the fixed `mastodon.social` [hashtag timeline](https://docs.joinmastodon.org/methods/timelines/#tag). Enter one hashtag without spaces. Fetches at most 40 public statuses and strips HTML before analysis. Private/unlisted statuses are not imported.

If public preview is disabled, configure `MASTODON_TOKEN` with an appropriately authorized token for that same server. This token stays in the server environment and is never returned to the browser or stored in a job payload. No arbitrary instance URL is accepted from workspace users. This release does not implement full-text Mastodon search, OAuth onboarding, or federated crawling.

## YouTube

Set `ENABLE_YOUTUBE=1` and configure `YOUTUBE_API_KEY` in your server environment. The key must belong to a Google project with the YouTube Data API enabled and appropriate quota/access. Never commit the key.

Enter an 11-character video ID. The fixed [commentThreads list endpoint](https://developers.google.com/youtube/v3/docs/commentThreads/list) retrieves at most 100 recent top-level comments for that video in plain text. Replies, full channel history and multi-page crawling are not included. Videos with disabled comments, quota exhaustion, restricted API keys or access restrictions may fail; the job records a redacted error. The browser never receives the API key. A call consumes provider quota.

## Evidence and errors

Mastodon and YouTube imports preserve source URLs and provider IDs with the original text. Source links open only through an explicit user click. Transport failures, 429s and server errors are retried up to three attempts with bounded backoff. Permanent errors stop processing. Exceptions shown to users omit provider response bodies and secret-bearing request URLs.

Automated tests mock provider payloads, malformed inputs, retry behavior, credential redaction and workspace ingestion. Real YouTube collection requires your API credentials. These tests do not establish that a provider is currently reachable or that an account has permission. Do not enable automated high-volume collection without reviewing the provider's access rules and retention requirements.
