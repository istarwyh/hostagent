"""Shared validation for assistant and per-run graph configuration."""

from typing import Annotated

from pydantic import AfterValidator


def validate_config(value: dict) -> dict:
    """Reject invalid graph configuration at the HTTP request boundary."""
    if not isinstance(value.get("configurable", {}), dict):
        raise ValueError("config.configurable must be an object")
    if "recursion_limit" in value:
        limit = value["recursion_limit"]
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("config.recursion_limit must be a positive integer")
    return value


GraphConfig = Annotated[dict, AfterValidator(validate_config)]
