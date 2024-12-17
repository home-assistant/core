"""Enforce that the integration has strict typing enabled.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/strict-typing/
"""

from functools import lru_cache
from importlib import metadata
from pathlib import Path
import re

from script.hassfest.model import Config, Integration

_STRICT_TYPING_FILE = Path(".strict-typing")
_COMPONENT_REGEX = r"homeassistant.components.([^.]+).*"


@lru_cache
def _strict_typing_components(strict_typing_file: Path) -> set[str]:
    return set(
        {
            match.group(1)
            for line in strict_typing_file.read_text(encoding="utf-8").splitlines()
            if (match := re.match(_COMPONENT_REGEX, line)) is not None
        }
    )


def _check_requirements_are_typed(integration: Integration) -> str | None:
    """Check if all requirements are typed."""
    for requirement in integration.requirements:
        requirement_name, requirement_version = requirement.split("==")
        try:
            distribution = metadata.distribution(requirement_name)
        except metadata.PackageNotFoundError:
            # Package not installed locally
            continue
        if distribution.version != requirement_version:
            # Version out of date locally
            continue

        if not any(file for file in distribution.files if file.name == "py.typed"):
            # no py.typed file
            return requirement
        return None
    return None


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration has strict typing enabled."""
    strict_typing_file = config.root / _STRICT_TYPING_FILE

    if integration.domain not in _strict_typing_components(strict_typing_file):
        return [
            "Integration does not have strict typing enabled "
            "(is missing from .strict-typing)"
        ]
    if untyped_requirement := _check_requirements_are_typed(integration):
        return [
            f"Requirement '{untyped_requirement}' appears untyped (missing py.typed)"
        ]
    return None
