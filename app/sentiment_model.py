"""Pinned CPU transformer inference, loaded only when explicitly configured."""
import hashlib
import json
import os
from functools import lru_cache
from .model_setup import MODEL_DIR, MODEL_SHA256, REVISION

SUPPORTED = {'ar', 'en', 'fr', 'de', 'hi', 'it', 'es', 'pt', 'und'}


def provider():
    value = os.environ.get('SENTIMENT_PROVIDER', 'baseline')
    if value not in ('baseline', 'onnx'):
        raise ValueError('SENTIMENT_PROVIDER must be baseline or onnx.')
    return value


@lru_cache(maxsize=1)
def load_model():
    import onnxruntime as ort
    from tokenizers import Tokenizer
    path = MODEL_DIR / 'onnx' / 'model_quantized.onnx'
    if not (MODEL_DIR / 'manifest.json').exists():
        raise ValueError('Multilingual model missing. Run python -m app.model_setup first.')
    manifest = json.loads((MODEL_DIR / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('revision') != REVISION:
        raise ValueError('Model revision does not match this release.')
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != MODEL_SHA256:
            raise ValueError('Model checksum mismatch. Run model setup again.')
    tokenizer = Tokenizer.from_file(str(MODEL_DIR / 'tokenizer.json'))
    tokenizer.enable_truncation(max_length=256)
    options = ort.SessionOptions(); options.intra_op_num_threads = 2; options.inter_op_num_threads = 1
    model = ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
    config = json.loads((MODEL_DIR / 'config.json').read_text(encoding='utf-8'))
    labels = {int(k): v.lower() for k, v in config['id2label'].items()}
    if set(labels.values()) != {'negative', 'neutral', 'positive'}:
        raise ValueError('Unexpected sentiment model label mapping.')
    return tokenizer, model, labels


def predict(text, language):
    if language not in SUPPORTED:
        return {'sentiment': 'unclassified', 'score': None, 'probabilities': {}, 'model': 'xlm-roberta-onnx-q8@'+REVISION[:12]}
    import numpy as np
    tokenizer, model, labels = load_model()
    normalized = ' '.join('@user' if t.startswith('@') and len(t)>1 else 'http' if t.startswith('http') else t for t in text.split())
    encoded = tokenizer.encode(normalized)
    values = {'input_ids': encoded.ids, 'attention_mask': encoded.attention_mask, 'token_type_ids': encoded.type_ids}
    inputs = {item.name: np.asarray([values[item.name]], dtype=np.int64) for item in model.get_inputs()}
    logits = np.asarray(model.run(None, inputs)[0][0], dtype=np.float64)
    if logits.shape != (3,) or not np.isfinite(logits).all():
        raise ValueError('Invalid model output.')
    probabilities = np.exp(logits-logits.max()); probabilities /= probabilities.sum()
    label = labels[int(probabilities.argmax())]
    return {'sentiment': label, 'score': float(probabilities[2]-probabilities[0]),
            'probabilities': {labels[i]: float(p) for i,p in enumerate(probabilities)},
            'model': 'xlm-roberta-onnx-q8@'+REVISION[:12], 'truncation_limit': 256}


def status():
    current = provider()
    return {'provider': current, 'model': 'xlm-roberta-onnx-q8@'+REVISION[:12] if current == 'onnx' else 'vader-3.3.2-domain-v1',
            'languages': sorted(SUPPORTED-{'und'}) if current == 'onnx' else ['en'],
            'description': 'Local multilingual transformer · 8 supported languages' if current == 'onnx' else 'Local English VADER sentiment · other languages unclassified'}
