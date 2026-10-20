# Local generative research

Social Ear supports an optional local [Ollama chat API](https://docs.ollama.com/api/chat) provider using [structured JSON output](https://docs.ollama.com/capabilities/structured-outputs). The default remains extractive, so the application works without a language-model service.

If you cannot install Ollama, use the [hosted Groq provider](GROQ.md) instead. It requires a server-side API key and sends bounded evidence excerpts to Groq.

Install Ollama from its official distribution and install a local model that supports structured output, for example `ollama pull qwen2.5:1.5b`. Then run:

```powershell
$env:RESEARCH_PROVIDER='ollama'
$env:OLLAMA_MODEL='qwen2.5:1.5b'
$env:OLLAMA_URL='http://127.0.0.1:11434'
.venv/Scripts/python -m app
```

The service must already be running. Social Ear does not install, download, or start a generative model in response to an HTTP request. Model memory and response time depend on your machine. The current development environment does not have Ollama installed, so provider behavior has automated mocked coverage, not a live generation test.

Docker Compose points the app to `http://host.docker.internal:11434` on a host running Ollama. The host service must be reachable from Docker. Keep the service restricted to trusted local clients; it has no app-level authentication here. Docker Linux hosts may need an explicit host-gateway mapping or an alternate deployment arrangement.

## Evidence flow

1. Retrieve at most five workspace posts by textual relevance.
2. Limit each excerpt to 2,000 characters and send only those excerpts plus the question to the configured local service.
3. Request at most five structured claims, each containing existing evidence IDs.
4. Validate output shape and require every citation ID to exist in the retrieved evidence set. Reject missing/unknown citations, incomplete responses and malformed output.
5. Display accepted claims together with original source text and a review notice.

Post text is marked untrusted in the prompt. No tools or external browsing are available to the model. The local endpoint is restricted to loopback or Docker's host bridge on port 11434; browser users cannot choose another destination. Inputs are not sent to a cloud AI service. Generated claims can still be wrong or misrepresent cited text. Citation validation proves the IDs exist, not semantic entailment. Never treat a cited answer as automatically verified.
