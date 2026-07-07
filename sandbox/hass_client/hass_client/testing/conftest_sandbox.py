"""Real-subprocess pytest plugin for sandbox compat tests.

Exercises the production code path end-to-end: the test HA's
``sandbox`` integration spawns ``python -m hass_client.sandbox``
as a real subprocess and talks to it over the JSON-line stdio
:class:`Channel`. Slower than the in-process plugin (per-sandbox
subprocess startup) but pins the subprocess boundary.

Freezer incompatibility
-----------------------

Tests that use the ``freezer`` fixture (pytest-freezer) cannot use this
plugin: ``freezer.move_to(...)`` advances time inside the test process,
but the subprocess's clock is untouched, so any time-sensitive code
inside the sandbox hangs the channel. Mark such tests::

    @pytest.mark.no_sandbox_freezer
    def test_foo(freezer): ...

The plugin auto-skips those tests rather than v1's silent fallback, so
the compat report shows them explicitly as ``skipped`` and reviewers
know they need attention.

Usage::

    pytest -p hass_client.testing.conftest_sandbox <test path>

The plugin exposes the ``sandbox_subprocess`` fixture, which yields
a :class:`SubprocessSandbox` handle once the subprocess is running.
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

from hass_client.testing._autotag import configure_compat_plugin, engagement_count

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
        f"sandbox-compat: router entry_setup engaged {engagement_count()} time(s)"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-skip tests that combine the ``freezer`` fixture with the subprocess plugin.

    The pytest-freezer fixture moves time inside the test process only;
    the sandbox subprocess's clock is unaffected, so a test that calls
    ``freezer.move_to(...)`` and waits on a sandbox-side timer will
    deadlock. Skip explicitly so the compat report shows the gap rather
    than silently falling back.

    Tests that explicitly opt out via :data:`_MARK_NO_FREEZER` are
    skipped without inspection — they have already declared incompatible.
    """
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
    """Handle for one running sandbox subprocess.

    Exposed so tests can read ``.pid`` / ``.state`` for assertions and
    ``await .stop()`` early. The fixture's teardown always calls
    :meth:`stop` whether or not the test does.
    """

    group: str
    manager: object  # SandboxManager — typed loosely to keep imports lazy

    async def stop(self) -> None:
        """Issue a graceful shutdown, then SIGTERM/SIGKILL escalation."""
        # The integration's EVENT_HOMEASSISTANT_STOP listener will run
        # the same teardown on hass shutdown, but the compat suite tears
        # down the sandbox before hass to surface subprocess crashes in
        # the right place. ``async_stop_all`` is idempotent.
        # Lazy import: testing package must not pull the HA integration
        # tree at import time.
        from homeassistant.components.sandbox.manager import (  # noqa: PLC0415
            SandboxManager,
        )

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
    """Set up ``sandbox`` and spawn a real subprocess for ``group``.

    Unlike :func:`hass_client.testing.pytest_plugin.async_setup_inprocess_sandbox`,
    this hands control to the integration's default
    :class:`SandboxManager` — the subprocess is spawned by
    :meth:`SandboxManager.ensure_started` as it would be in production.
    """
    # Lazy import: testing package must not pull the HA integration
    # tree at import time.
    from homeassistant.components.sandbox.const import DATA_SANDBOX  # noqa: PLC0415
    from homeassistant.setup import async_setup_component  # noqa: PLC0415

    assert await async_setup_component(hass, "sandbox", {})
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
