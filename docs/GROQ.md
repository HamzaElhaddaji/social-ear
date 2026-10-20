# Hosted research with Groq

Groq is an optional hosted research provider using its [structured outputs API](https://console.groq.com/docs/structured-outputs). No Ollama installation is needed. Sentiment/topic analysis remains local; research questions and up to five matching excerpts (each at most 2,000 characters) are sent to Groq only when a user asks the research assistant. The workspace interface discloses this before submission.

## Configure without exposing the key

```powershell
.venv/Scripts/python -m app.configure_groq
.venv/Scripts/python -m app
```

The configuration command reads the key through hidden input and saves it in the Git-ignored `.env` file. It refuses to save if Git is not ignoring that file. It selects `RESEARCH_PROVIDER=groq` and defaults to `GROQ_MODEL=openai/gpt-oss-20b`. CLI launches load `.env`; existing process variables take precedence. Do not print, commit or share `.env`. It contains plaintext secrets on this local machine and should be protected like other credentials. Replace a key that has been pasted into chat or exposed elsewhere, then rerun the configuration command.

Docker Compose forwards `GROQ_API_KEY` and `GROQ_MODEL` from `.env` to the backend only. The key is never sent to browser JavaScript, API responses or job payloads. The API destination is fixed to `https://api.groq.com`; redirects are disabled. Errors omit response bodies and credential-bearing exception text.

## Cost and validation

Use your provider's free plan and [check its current limits](https://console.groq.com/docs/rate-limits). A key alone does not establish the account's plan or guarantee zero billing. Social Ear does not upgrade your plan, change billing, automatically switch to another model or retry a quota failure. Each research request is bounded to 1,600 output tokens. Authentication, quota and provider errors are displayed clearly.

The server validates structured claims and rejects citation IDs outside the retrieved workspace evidence set. This does not prove semantic accuracy. Users must review original excerpts. If no evidence matches, no hosted request is made. Local extractive mode remains available with `RESEARCH_PROVIDER=extractive`.
