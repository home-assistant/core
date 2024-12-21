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


def _check_requirements_are_typed(integration: Integration) -> list[str]:
    """Check if all requirements are typed."""
    invalid_requirements = []
    for requirement in integration.requirements:
        requirement_name, requirement_version = requirement.split("==")
        # Remove any extras
        requirement_name = requirement_name.split("[")[0]
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
            invalid_requirements.append(requirement)

    return invalid_requirements


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
    if untyped_requirements := _check_requirements_are_typed(integration):
        return [
            f"Requirements {untyped_requirements} do not conform PEP 561 (https://peps.python.org/pep-0561/)",
            "They should be typed and have a 'py.typed' file",
        ]
    return None
