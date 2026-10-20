"""Small non-executing .env reader for CLI launches; process variables win."""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_local_config(path=None):
    path = Path(path) if path else ROOT / '.env'
    if not path.exists():return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        key,sep,value=line.partition('=')
        key=key.strip();value=value.strip()
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key):continue
        if value.startswith('"'):
            value=json.loads(value)
            if not isinstance(value,str):raise ValueError('Configuration values must be strings.')
        elif len(value)>=2 and value[0]==value[-1]=="'":value=value[1:-1]
        os.environ.setdefault(key,value)
