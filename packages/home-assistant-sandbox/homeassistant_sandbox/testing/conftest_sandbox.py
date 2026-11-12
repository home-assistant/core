"""Real-subprocess pytest plugin for sandbox compat tests."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

from homeassistant_sandbox.testing._autotag import (
    configure_compat_plugin,
    engagement_count,
    tagged_count,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DEFAULT_GROUP = "built-in"

_MARK_NO_FREEZER = "no_sandbox_freezer"

_unconfigure: Callable[[], None] | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Register the freezer marker; install autotag + engagement counter."""
    config.addinivalue_line(
        "markers",
        f"{_MARK_NO_FREEZER}: skip the test when the real-subprocess sandbox"
        " plugin is active (freezer + subprocess clock skew hangs the channel)",
    )
    global _unconfigure  # noqa: PLW0603
    if _unconfigure is None:
        _unconfigure = configure_compat_plugin()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Restore the patched hooks on session exit."""
    global _unconfigure  # noqa: PLW0603
    if _unconfigure is not None:
        _unconfigure()
        _unconfigure = None


def pytest_terminal_summary(
    terminalreporter: Any, exitstatus: int, config: pytest.Config
) -> None:
    """Report how often the sandbox router actually engaged (see run_compat)."""
    terminalreporter.write_line(
        f"sandbox-compat: router entry_setup engaged {engagement_count()} time(s),"
        f" {tagged_count()} entries tagged"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-skip tests that combine the ``freezer`` fixture with the subprocess plugin."""
    skip_freezer = pytest.mark.skip(
        reason=(
            "freezer fixture is incompatible with the real-subprocess"
            " sandbox plugin (subprocess clock can't be advanced)"
        )
    )
    for item in items:
        if item.get_closest_marker(_MARK_NO_FREEZER) is not None:
            item.add_marker(skip_freezer)
            continue
        fixtures = getattr(item, "fixturenames", None)
        if fixtures is None:
            continue
        if "freezer" in fixtures:
            item.add_marker(skip_freezer)
            continue
        # Inject the subprocess sandbox into every hass-using test — the
        # autotag alone leaves ``hass.config_entries.router`` None, and a
        # tagged entry then quietly sets up locally (lane no-op).
        if "hass" in fixtures and "sandbox_subprocess" not in fixtures:
            fixtures.append("sandbox_subprocess")


@dataclass
class SubprocessSandbox:
    """Handle for one running sandbox subprocess."""

    group: str
    manager: object  # SandboxManager — typed loosely to keep imports lazy

    async def stop(self) -> None:
        """Issue a graceful shutdown, then SIGTERM/SIGKILL escalation."""
        # Stop the worker before hass teardown so failures are attributed to this fixture.
        from homeassistant.components.sandbox.manager import SandboxManager  # noqa: PLC0415

        assert isinstance(self.manager, SandboxManager)
        await self.manager.async_graceful_shutdown_all(
            timeout=self.manager.shutdown_grace
        )
        await self.manager.async_stop_all()


async def async_setup_subprocess_sandbox(
    hass: HomeAssistant,
    *,
    group: str = DEFAULT_GROUP,
) -> SubprocessSandbox:
    """Set up ``sandbox`` and spawn a real subprocess for ``group``."""
    # Lazy import: testing package must not pull the HA integration
    # tree at import time.
    from homeassistant.components.sandbox import async_setup_runtime  # noqa: PLC0415
    from homeassistant.components.sandbox.const import DATA_SANDBOX  # noqa: PLC0415

    await async_setup_runtime(hass, domains=None)
    data = hass.data[DATA_SANDBOX]
    manager = data.manager
    if manager is None:  # pragma: no cover — defensive only
        raise RuntimeError("sandbox setup did not install a manager")
    await manager.ensure_started(group)
    return SubprocessSandbox(group=group, manager=manager)


@pytest_asyncio.fixture
async def sandbox_subprocess(
    hass: HomeAssistant,
) -> AsyncIterator[SubprocessSandbox]:
    """Set up the ``sandbox`` integration and spawn a real built-in sandbox."""
    sandbox = await async_setup_subprocess_sandbox(hass, group=DEFAULT_GROUP)
    try:
        yield sandbox
    finally:
        await sandbox.stop()


__all__ = [
    "DEFAULT_GROUP",
    "SubprocessSandbox",
    "async_setup_subprocess_sandbox",
    "sandbox_subprocess",
]
