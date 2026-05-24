"""Real-subprocess pytest plugin for sandbox_v2 compat tests.

Exercises the production code path end-to-end: the test HA's
``sandbox_v2`` integration spawns ``python -m hass_client.sandbox_v2``
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

The plugin exposes the ``sandbox_v2_subprocess`` fixture, which yields
a :class:`SubprocessSandbox` handle once the subprocess is running.
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from hass_client.testing._autotag import install_mock_config_entry_autotag

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DEFAULT_GROUP = "built-in"

_MARK_NO_FREEZER = "no_sandbox_freezer"

_unpatch_autotag: Callable[[], None] | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``no_sandbox_freezer`` marker and install the autotag patch."""
    config.addinivalue_line(
        "markers",
        f"{_MARK_NO_FREEZER}: skip the test when the real-subprocess sandbox"
        " plugin is active (freezer + subprocess clock skew hangs the channel)",
    )
    global _unpatch_autotag  # noqa: PLW0603
    if _unpatch_autotag is None:
        _unpatch_autotag = install_mock_config_entry_autotag()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Restore the original ``MockConfigEntry.add_to_hass`` on session exit."""
    global _unpatch_autotag  # noqa: PLW0603
    if _unpatch_autotag is not None:
        _unpatch_autotag()
        _unpatch_autotag = None


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
        fixtures = getattr(item, "fixturenames", ())
        if "freezer" in fixtures:
            item.add_marker(skip_freezer)


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
        from homeassistant.components.sandbox_v2.manager import (  # noqa: PLC0415
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
    """Set up ``sandbox_v2`` and spawn a real subprocess for ``group``.

    Unlike :func:`hass_client.testing.pytest_plugin.async_setup_inprocess_sandbox`,
    this hands control to the integration's default
    :class:`SandboxManager` — the subprocess is spawned by
    :meth:`SandboxManager.ensure_started` as it would be in production.
    """
    # Lazy import: testing package must not pull the HA integration
    # tree at import time.
    from homeassistant.components.sandbox_v2.const import (  # noqa: PLC0415
        DATA_SANDBOX_V2,
    )
    from homeassistant.setup import async_setup_component  # noqa: PLC0415

    assert await async_setup_component(hass, "sandbox_v2", {})
    data = hass.data[DATA_SANDBOX_V2]
    manager = data.manager
    if manager is None:  # pragma: no cover — defensive only
        raise RuntimeError("sandbox_v2 setup did not install a manager")
    await manager.ensure_started(group)
    return SubprocessSandbox(group=group, manager=manager)


@pytest_asyncio.fixture
async def sandbox_v2_subprocess(
    hass: HomeAssistant,
) -> AsyncIterator[SubprocessSandbox]:
    """Set up the ``sandbox_v2`` integration and spawn a real built-in sandbox."""
    sandbox = await async_setup_subprocess_sandbox(hass, group=DEFAULT_GROUP)
    try:
        yield sandbox
    finally:
        await sandbox.stop()


__all__ = [
    "DEFAULT_GROUP",
    "SubprocessSandbox",
    "async_setup_subprocess_sandbox",
    "sandbox_v2_subprocess",
]
