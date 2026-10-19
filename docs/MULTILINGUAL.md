# Local multilingual sentiment

The optional CPU backend uses the quantized [ONNX export](https://huggingface.co/onnx-community/twitter-xlm-roberta-base-sentiment-ONNX) of [Cardiff NLP's multilingual sentiment model](https://huggingface.co/cardiffnlp/twitter-xlm-roberta-base-sentiment). The original model was fine-tuned on Arabic, English, French, German, Hindi, Italian, Spanish and Portuguese. Other detected languages remain unclassified in Social Ear. Short text may have undetermined language.

## Install and enable

```powershell
.venv/Scripts/python -m pip install -r requirements-models.txt
.venv/Scripts/python -m app.model_setup
$env:SENTIMENT_PROVIDER='onnx'
.venv/Scripts/python -m app
```

Setup downloads about 300 MB of model/tokenizer assets from a pinned Hugging Face revision. Model bytes are verified against the upstream SHA-256. Files remain in ignored `data/models/sentiment/`; weights are not committed to Git. Setup downloads public files without an authentication token. The application never downloads a model during an HTTP request. Inference uses CPU only and does not send post text to a remote service. Missing or invalid configured model assets stop startup rather than silently switching analysis providers.

For Docker, run model setup on the host, set `INSTALL_MODELS=1` and `SENTIMENT_PROVIDER=onnx` in `.env`, then `docker compose up --build -d`. Compose mounts the host model folder read-only. Keep the default `baseline` configuration for the smaller dependency footprint.

## Behavior and limits

Model outputs contain a pinned model identifier and three normalized class probabilities. These probabilities are not calibrated accuracy guarantees. The scalar `score` is positive-class minus negative-class probability, not the probability of the winning label. Input is truncated to 256 tokens; long conversations can lose context. User handles and URLs are normalized per the original model guidance. Aspect estimates remain English heuristics and are marked unclassified for non-English text.

Existing records retain their original analysis metadata. Use **Reanalyze unreviewed conversations** to apply the selected provider. Human-reviewed labels and investigation notes are preserved.

## Test

```powershell
$env:RUN_MODEL_TESTS='1'
.venv/Scripts/python -m unittest discover -s tests -p test_models.py -v
```

The live suite checks eight straightforward examples across five languages. This is an inference smoke test, not a representative accuracy benchmark. Standard CI uses mocked model integration and does not download large weights. A held-out social dataset remains necessary for measuring production performance.
