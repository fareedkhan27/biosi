"""Top-level ASGI entrypoint.

Allows running the API with either:
- `uvicorn main:app`
- `uvicorn Biosi.main:app`
- `uvicorn app.main:app`
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app

__all__ = ["app"]
