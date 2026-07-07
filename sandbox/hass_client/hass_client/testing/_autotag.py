"""Auto-tag :class:`MockConfigEntry` with the sandbox group at ``add_to_hass``.

Without this patch, vanilla HA Core integration tests build their
``MockConfigEntry`` instances with no sandbox tag, so the sandbox
router's classifier path never fires — the entry sets up locally and
the sandbox bridge is bypassed entirely.

The compat plugins install this monkey-patch in ``pytest_configure`` so
every ``MockConfigEntry.add_to_hass(hass)`` call run under the plugin
classifies the entry's domain and, if it routes to a sandbox group,
sets :attr:`ConfigEntry.sandbox` to the matching group name before
the original ``add_to_hass`` adds it to the manager. Setting the
field rather than mutating ``entry.data`` keeps the autotag invisible
to integration tests that assert on data contents.

The classifier here is a synchronous filesystem-only re-implementation
of :func:`homeassistant.components.sandbox.classifier.classify`.
Calling the real async classifier from the sync ``add_to_hass`` would
require driving a coroutine from inside a running event loop, which is
already where compat tests are. The duplicated logic is small (~30 LOC)
and exercised by every compat run.
"""

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
    """Return the sandbox group for ``domain``, or ``None`` for main.

    Mirrors :func:`homeassistant.components.sandbox.classifier.classify`
    but reads ``manifest.json`` + the integration directory contents
    directly so it can be called from a sync context.
    """
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


_ENGAGEMENT = {"entry_setups": 0}


def engagement_count() -> int:
    """Router-driven sandbox ``entry_setup`` count for this pytest session."""
    return _ENGAGEMENT["entry_setups"]


def install_router_engagement_counter() -> Callable[[], None]:
    """Count every router-driven sandbox entry setup.

    The compat lane's honesty guard: a run whose counter stays at zero
    never routed anything through a sandbox, so ``run_compat.py`` can
    flag it as a no-op instead of reporting vanilla-test results as
    sandbox compatibility. Idempotent; returns an unpatch callable.
    """
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
    """Install the autotag patch + engagement counter; returns the undo.

    Shared by both compat plugins' ``pytest_configure`` so the install /
    restore pairing lives in one place.
    """
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
    # Lazy import: ``tests.common`` is only importable when pytest is
    # running with HA Core's tests/ tree on the path. ``tests`` is the
    # HA Core test tree and this module is part of the compat plugin —
    # the TID251 ban on importing ``tests`` doesn't apply.
    from tests.common import MockConfigEntry  # noqa: PLC0415, TID251

    if getattr(MockConfigEntry, "_sandbox_autotag_patched", False):
        return lambda: None

    original = MockConfigEntry.add_to_hass

    def patched(self: Any, hass: HomeAssistant) -> None:
        if self.sandbox is None:
            group = classify_domain_sync(self.domain)
            if group is not None:
                # ``ConfigEntry`` enforces ``sandbox`` updates via
                # ``async_update_entry``; in tests the entry hasn't been
                # registered yet so we mirror the framework's
                # ``object.__setattr__`` trick directly.
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
]
