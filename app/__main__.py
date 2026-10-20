import os
import uvicorn
from .config import load_local_config
load_local_config()
from .api import create_app

if __name__ == '__main__':
    uvicorn.run(create_app(), host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '8000')), log_level='info')
