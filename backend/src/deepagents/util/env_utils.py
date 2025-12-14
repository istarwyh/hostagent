import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def from_env(keys: list[str], default: str) -> str:
    for key in keys:
        if os.environ.get(key):
            return os.environ[key]
    return default
