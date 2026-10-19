"""Explicit, pinned model download. Never called by an HTTP request."""
import hashlib
import json
from pathlib import Path

REPOSITORY = 'onnx-community/twitter-xlm-roberta-base-sentiment-ONNX'
REVISION = '3112e85dea04f0019bf01282916588e3c9dd9bc8'
MODEL_SHA256 = '6c7c4e804129149d58eb1d11a576129f4270f46134dd074315b8aea05d178e20'
MODEL_DIR = Path(__file__).resolve().parent.parent / 'data' / 'models' / 'sentiment'


def setup():
    from huggingface_hub import snapshot_download
    snapshot_download(REPOSITORY, revision=REVISION, local_dir=MODEL_DIR,
                      allow_patterns=['config.json', 'tokenizer.json', 'onnx/model_quantized.onnx'], token=False)
    path = MODEL_DIR / 'onnx' / 'model_quantized.onnx'
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != MODEL_SHA256:
        raise RuntimeError('Downloaded model checksum mismatch. Model was not enabled.')
    (MODEL_DIR / 'manifest.json').write_text(json.dumps({'repository': REPOSITORY, 'revision': REVISION, 'sha256': digest}), encoding='utf-8')
    print(f'Multilingual CPU model verified: {MODEL_DIR}')
    print('Set SENTIMENT_PROVIDER=onnx and restart Social Ear. No post data leaves this server.')


if __name__ == '__main__':
    setup()
