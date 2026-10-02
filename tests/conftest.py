"""Make the Project importable with no .env, as in CI.

Runs before any test module, so before the first import of the Project.
"""

import os

import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False

os.environ.setdefault("LLM_BASE_URL", "http://llm.invalid/v1")
os.environ.setdefault("LLM_API_KEY", "dummy-key")
os.environ.setdefault("LLM_MODEL", "dummy-model")
