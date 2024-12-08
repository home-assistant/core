"""Enforce that the integration has strict typing enabled.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/strict-typing/
"""

from functools import lru_cache
from pathlib import Path
import re

from script.hassfest.model import Integration

_STRICT_TYPING_FILE = Path(".strict-typing")
_COMPONENT_REGEX = r"homeassistant.components.([^.]+).*"


@lru_cache
def _strict_typing_components() -> set[str]:
    return set(
        {
            match.group(1)
            for line in _STRICT_TYPING_FILE.read_text(encoding="utf-8").splitlines()
            if (match := re.match(_COMPONENT_REGEX, line)) is not None
        }
    )


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration has strict typing enabled."""

    if integration.domain not in _strict_typing_components():
        return [
            "Integration does not have strict typing enabled "
            "(is missing from .strict-typing)"
        ]
    return None
