"""Routing rules: which sandbox should host a given integration?

`classify(integration)` is a pure function from a loaded `Integration`
(manifest + on-disk shape) to a `SandboxAssignment`. It is called by the
config-flow router and by config-entry setup interception — every
decision about "main vs sandbox" funnels through here.

Rule order (first match wins):

1. `integration_type == "system"` → Main. System integrations are part of
   the HA runtime; sandboxing them is meaningless.
2. `domain in ALWAYS_MAIN` → Main. Hand-picked deny-list for integrations
   the bridge cannot host correctly today (see `const.py` for the why).
3. Any platform file in `SANDBOX_INCOMPATIBLE_PLATFORMS` → Main. Platform-
   level deny-list for shapes the websocket bridge can't ferry yet.
4. Custom (non-built-in) integration → `Sandbox("custom")`.
5. Otherwise → `Sandbox("built-in")`.

The check uses `Integration.platforms_exists()` so we never have to import
the integration to classify it.
"""

from dataclasses import dataclass
from typing import Final

from homeassistant.const import BASE_PLATFORMS
from homeassistant.loader import Integration

from .const import ALWAYS_MAIN, SANDBOX_INCOMPATIBLE_PLATFORMS

GROUP_BUILT_IN: Final = "built-in"
GROUP_CUSTOM: Final = "custom"


@dataclass(frozen=True, slots=True)
class SandboxAssignment:
    """Where an integration should run.

    `group is None` means "stay on main"; otherwise it's the name of the
    sandbox process that should host the integration.
    """

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
