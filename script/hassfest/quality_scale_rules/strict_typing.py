"""Enforce that the integration has strict typing enabled."""

from functools import cache
import pathlib
import re

from . import QualityScaleCheck

STRICT_TYPING_FILE = pathlib.Path(".strict-typing")
COMPONENT_PREFIX = r"homeassistant.components.([^.]+).*"


@cache
def _strict_typing_components() -> set[str]:
    return set(
        {
            match.group(1)
            for line in STRICT_TYPING_FILE.read_text().splitlines()
            if (match := re.match(COMPONENT_PREFIX, line)) is not None
        }
    )


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration has strict typing enabled."""

    if check.integration.domain not in _strict_typing_components():
        check.add_error(
            "strict-typing",
            "Integration does not require strict typing (is missing from .strict-typing)",
        )
