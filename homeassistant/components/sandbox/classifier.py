"""Routing rules: which sandbox should host a given integration?"""

from dataclasses import dataclass
from typing import Final

from homeassistant.const import BASE_PLATFORMS
from homeassistant.loader import Integration

from .const import ALWAYS_MAIN, SANDBOX_INCOMPATIBLE_PLATFORMS

GROUP_BUILT_IN: Final = "built-in"
GROUP_CUSTOM: Final = "custom"


@dataclass(frozen=True, slots=True)
class SandboxAssignment:
    """Where an integration should run."""

    group: str | None

    @property
    def is_main(self) -> bool:
        """Return True if the integration runs on main."""
        return self.group is None


MAIN: Final = SandboxAssignment(group=None)


def _sandbox(group: str) -> SandboxAssignment:
    return SandboxAssignment(group=group)


def classify(integration: Integration) -> SandboxAssignment:
    """Return the sandbox assignment for an integration."""
    if integration.integration_type == "system":
        return MAIN

    if integration.domain in ALWAYS_MAIN:
        return MAIN

    incompatible = (
        set(integration.platforms_exists(BASE_PLATFORMS))
        & SANDBOX_INCOMPATIBLE_PLATFORMS
    )
    if incompatible:
        return MAIN

    if not integration.is_built_in:
        return _sandbox(GROUP_CUSTOM)

    return _sandbox(GROUP_BUILT_IN)
