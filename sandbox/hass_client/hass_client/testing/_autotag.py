"""Auto-tag :class:`MockConfigEntry` with the sandbox group at ``add_to_hass``."""

from collections.abc import Callable
import contextlib
import json
import pathlib
from typing import TYPE_CHECKING, Any

import homeassistant
from homeassistant.components.sandbox.classifier import GROUP_BUILT_IN, GROUP_CUSTOM
from homeassistant.components.sandbox.const import (
    ALWAYS_MAIN,
    SANDBOX_INCOMPATIBLE_PLATFORMS,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_HASS_COMPONENTS_DIR = pathlib.Path(homeassistant.__file__).parent / "components"


def classify_domain_sync(domain: str) -> str | None:
    """Return the sandbox group for ``domain``, or ``None`` for main."""
    if domain in ALWAYS_MAIN:
        return None
    component_dir = _HASS_COMPONENTS_DIR / domain
    manifest_path = component_dir / "manifest.json"
    if not manifest_path.is_file():
        return GROUP_CUSTOM
    try:
        manifest = json.loads(manifest_path.read_text())
    except OSError, json.JSONDecodeError:
        return None
    if manifest.get("integration_type") == "system":
        return None
    for platform in SANDBOX_INCOMPATIBLE_PLATFORMS:
        if (component_dir / f"{platform}.py").is_file():
            return None
    return GROUP_BUILT_IN


_ENGAGEMENT = {"entry_setups": 0, "tagged": 0}


def engagement_count() -> int:
    """Router-driven sandbox ``entry_setup`` count for this pytest session."""
    return _ENGAGEMENT["entry_setups"]


def tagged_count() -> int:
    """How many MockConfigEntry instances the autotag routed to a sandbox."""
    return _ENGAGEMENT["tagged"]


def install_router_engagement_counter() -> Callable[[], None]:
    """Count every router-driven sandbox entry setup."""
    # Lazy import: the HA integration tree must not load at plugin
    # import time (same rule as the classifier import below).
    from homeassistant.components.sandbox.router import (  # noqa: PLC0415
        SandboxFlowRouter,
    )

    if getattr(SandboxFlowRouter, "_sandbox_counter_patched", False):
        return lambda: None

    original = SandboxFlowRouter.async_setup_entry

    async def counted(self: Any, entry: Any) -> bool | None:
        try:
            result = await original(self, entry)
        except Exception:
            # Only routed entries raise — a failed remote setup still engaged.
            _ENGAGEMENT["entry_setups"] += 1
            raise
        if result is not None:
            _ENGAGEMENT["entry_setups"] += 1
        return result

    SandboxFlowRouter.async_setup_entry = counted
    SandboxFlowRouter._sandbox_counter_patched = True  # noqa: SLF001

    def restore() -> None:
        SandboxFlowRouter.async_setup_entry = original
        with contextlib.suppress(AttributeError):
            delattr(SandboxFlowRouter, "_sandbox_counter_patched")

    return restore


def configure_compat_plugin() -> Callable[[], None]:
    """Install the autotag patch + engagement counter; returns the undo."""
    unpatch_autotag = install_mock_config_entry_autotag()
    unpatch_counter = install_router_engagement_counter()

    def restore() -> None:
        unpatch_counter()
        unpatch_autotag()

    return restore


def install_mock_config_entry_autotag() -> Callable[[], None]:
    """Patch :meth:`MockConfigEntry.add_to_hass` to inject the sandbox group.

    Idempotent: calling twice is a no-op. Returns an unpatch callable.
    """
    # Core test helpers are available only when running inside the Core test suite.
    from tests.common import MockConfigEntry  # noqa: PLC0415, TID251

    if getattr(MockConfigEntry, "_sandbox_autotag_patched", False):
        return lambda: None

    original = MockConfigEntry.add_to_hass

    def patched(self: Any, hass: HomeAssistant) -> None:
        if self.sandbox is None:
            group = classify_domain_sync(self.domain)
            if group is not None:
                _ENGAGEMENT["tagged"] += 1
                # The test entry is not registered yet, so async_update_entry cannot update it.
                object.__setattr__(self, "sandbox", group)
        return original(self, hass)

    MockConfigEntry.add_to_hass = patched
    MockConfigEntry._sandbox_autotag_patched = True  # noqa: SLF001

    def restore() -> None:
        MockConfigEntry.add_to_hass = original
        with contextlib.suppress(AttributeError):
            delattr(MockConfigEntry, "_sandbox_autotag_patched")

    return restore


__all__ = [
    "classify_domain_sync",
    "configure_compat_plugin",
    "engagement_count",
    "install_mock_config_entry_autotag",
    "install_router_engagement_counter",
    "tagged_count",
]
