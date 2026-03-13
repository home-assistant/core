"""Enforce that the integration has strict typing enabled.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/strict-typing/
"""

from importlib import metadata
from pathlib import Path

from script.hassfest.model import Config, Integration, get_strict_typing_components

_STRICT_TYPING_FILE = Path(".strict-typing")


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
            try:
                metadata.distribution(f"types-{requirement_name}")
            except metadata.PackageNotFoundError:
                # also no stubs-only package
                invalid_requirements.append(requirement)

    return invalid_requirements


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration has strict typing enabled."""
    strict_typing_file = config.root / _STRICT_TYPING_FILE

    if integration.domain not in get_strict_typing_components(strict_typing_file):
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
