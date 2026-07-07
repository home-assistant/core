"""In-process pytest plugin for sandbox compat tests.

The plugin sets up the ``sandbox`` integration in the test HA, then
runs the sandbox-side :class:`hass_client.sandbox.SandboxRuntime` as an
asyncio task on the same loop, joined to the manager-side
:class:`Channel` via an in-memory loopback transport. No subprocess
spawn, no live socket — the same wire protocol the real sandbox uses,
but with bytes that never leave the process.

This is the "fast compat" lane: lower setup cost than spawning a
subprocess for every test, and freezer-fixture compatible. Tests that
need to verify the actual subprocess boundary should use
:mod:`hass_client.testing.conftest_sandbox` instead.

Usage::

    pytest -p hass_client.testing.pytest_plugin <test path>

The plugin exposes the ``sandbox_inprocess`` fixture, which yields
an :class:`InProcessSandbox` handle. The fixture sets up the
``sandbox`` integration in ``hass``, starts an in-process built-in
group sandbox, and tears everything down on exit.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
import contextlib
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

from hass_client.sandbox import SandboxRuntime
from hass_client.testing._autotag import configure_compat_plugin, engagement_count
from hass_client.testing._inproc import make_inproc_channel_pair

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DEFAULT_GROUP = "built-in"

_unconfigure: Callable[[], None] | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Install the autotag patch + router engagement counter."""
    global _unconfigure  # noqa: PLW0603
    if _unconfigure is None:
        _unconfigure = configure_compat_plugin()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Restore the patched hooks on session exit."""
    global _unconfigure  # noqa: PLW0603
    if _unconfigure is not None:
        _unconfigure()
        _unconfigure = None


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Inject the in-process sandbox into every ``hass``-using test.

    The autotag alone only marks entries with a group; with no sandbox
    set up, ``hass.config_entries.router`` stays ``None`` and every
    tagged entry quietly sets up locally — the lane measures nothing.
    Requesting the fixture here makes the router path real for each test.
    """
    for item in items:
        fixtures = getattr(item, "fixturenames", None)
        if fixtures is None or "hass" not in fixtures:
            continue
        if "sandbox_inprocess" not in fixtures:
            fixtures.append("sandbox_inprocess")


def pytest_terminal_summary(
    terminalreporter: Any, exitstatus: int, config: pytest.Config
) -> None:
    """Report how often the sandbox router actually engaged.

    ``run_compat.py`` parses this line; zero engagements on a suite that
    sets up config entries means the lane regressed to a no-op.
    """
    terminalreporter.write_line(
        f"sandbox-compat: router entry_setup engaged {engagement_count()} time(s)"
    )


@dataclass
class InProcessSandbox:
    """Handle for one running in-process sandbox.

    Most tests don't touch the handle directly — they get a wired ``hass``
    fixture and use the standard HA API. The handle is exposed for
    advanced tests that need to read runtime state (e.g. to assert which
    entries the sandbox loaded) or call :meth:`stop` early.
    """

    group: str
    runtime: SandboxRuntime
    runtime_task: asyncio.Task[int]
    channel: Any = None

    async def stop(self) -> None:
        """Gracefully shut the runtime down, then wait for the task.

        Issues the same ``sandbox/shutdown`` call production uses so
        entries unload and pending delay-saves flush — skipping it leaks
        the private hass's timers onto the shared test loop.
        """
        if self.channel is not None and not self.channel.closed:
            from hass_client.messages import MSG_SHUTDOWN  # noqa: PLC0415

            with contextlib.suppress(Exception):
                await asyncio.wait_for(
                    self.channel.call(MSG_SHUTDOWN, None), timeout=5.0
                )
        with contextlib.suppress(RuntimeError):
            self.runtime.request_shutdown()
        try:
            await asyncio.wait_for(self.runtime_task, timeout=5.0)
        except TimeoutError:
            self.runtime_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self.runtime_task
        except asyncio.CancelledError:
            pass


class _InProcessSandboxProcess:
    """Stand-in for :class:`SandboxProcess` that wraps an in-memory channel.

    The manager's :meth:`ensure_started` returns whatever is in its
    ``_sandboxes`` map for the group as long as the state is
    ``running``; the router only ever reads ``.channel`` and ``.state``.
    Mirroring those two attributes is enough to keep the rest of the
    integration's call path unchanged.
    """

    def __init__(self, group: str, channel: Any) -> None:
        """Pin the in-memory channel under this process stand-in."""
        self.group = group
        self._channel = channel
        self.state = "running"

    @property
    def channel(self) -> Any:
        """Return the manager-side channel."""
        return self._channel

    async def start(self) -> None:
        """No-op — the runtime is already running as an asyncio task."""

    async def stop(self) -> None:
        """No-op — the fixture owns the runtime task's lifecycle."""

    async def async_graceful_shutdown(self, *, timeout: float) -> bool:
        """Best-effort: issue a shutdown call so the runtime exits cleanly."""
        # Lazy import: testing package must not pull the HA integration
        # tree at import time.
        from homeassistant.components.sandbox.messages import (  # noqa: PLC0415
            MSG_SHUTDOWN,
        )

        try:
            await asyncio.wait_for(
                self._channel.call(MSG_SHUTDOWN, None), timeout=timeout
            )
        except Exception:  # noqa: BLE001
            return False
        return True


def _install_settling_block_till_done(
    hass: HomeAssistant, runtime: SandboxRuntime, mgr_channel: Any
) -> None:
    """Make main's ``async_block_till_done`` settle the sandbox round-trip.

    Vanilla integration tests assume local synchronous semantics: after
    ``await hass.async_block_till_done()`` they expect entities and states
    to be visible. With a sandbox in the middle, registrations and pushes
    are still in flight on the (same-loop) channel and the entity bridge's
    single-writer queue. Iterate until a pass sees the private hass idle,
    the bridge queue drained, and no channel dispatch task in flight, then
    settle main once more for anything late pushes scheduled.
    """
    original = hass.async_block_till_done

    async def settled(wait_background_tasks: bool = False) -> None:
        await original(wait_background_tasks=wait_background_tasks)
        rt_channel = runtime.channel
        # Wall-clock bound, not just an iteration cap: a pathological private
        # hass (timer churn from clock-jump tests) must cost each
        # block_till_done a couple of seconds at worst, not minutes.
        deadline = asyncio.get_running_loop().time() + 2.0
        for _ in range(200):
            if asyncio.get_running_loop().time() > deadline:
                break
            sandbox_hass = runtime.hass
            bridge = runtime.entity_bridge
            if sandbox_hass is not None:
                await sandbox_hass.async_block_till_done()
            if bridge is not None:
                await bridge.async_drain()
            if not mgr_channel._inflight and (  # noqa: SLF001
                rt_channel is None or not rt_channel._inflight  # noqa: SLF001
            ):
                await asyncio.sleep(0)
                if not mgr_channel._inflight and (  # noqa: SLF001
                    rt_channel is None or not rt_channel._inflight  # noqa: SLF001
                ):
                    break
            await asyncio.sleep(0)
        await original(wait_background_tasks=wait_background_tasks)

    hass.async_block_till_done = settled  # type: ignore[method-assign]


async def async_setup_inprocess_sandbox(
    hass: HomeAssistant,
    *,
    group: str = DEFAULT_GROUP,
    config_dir: str | None = None,
) -> InProcessSandbox:
    """Set up ``sandbox`` and run a sandbox runtime in-process.

    Returns an :class:`InProcessSandbox` handle whose
    :meth:`InProcessSandbox.stop` the caller is responsible for awaiting
    on teardown. Idempotent only insofar as a second call for the same
    ``group`` will collide with the first runtime — fixtures call once.
    """
    # Lazy import to keep ``hass_client.testing`` import-time free of HA
    # integration code (the testing package may be imported even when
    # the integration isn't installed).
    from homeassistant.components.sandbox.bridge import (  # noqa: PLC0415
        async_create_bridge,
    )
    from homeassistant.components.sandbox.const import DATA_SANDBOX  # noqa: PLC0415
    from homeassistant.setup import async_setup_component  # noqa: PLC0415

    assert await async_setup_component(hass, "sandbox", {})
    data = hass.data[DATA_SANDBOX]
    manager = data.manager
    if manager is None:  # pragma: no cover — defensive only
        raise RuntimeError("sandbox setup did not install a manager")

    mgr_channel, rt_channel = make_inproc_channel_pair(group=group)

    runtime = SandboxRuntime(
        url="ws://inprocess.invalid/api/websocket",
        group=group,
        config_dir=config_dir,
        channel_factory=_one_shot_channel_factory(rt_channel),
    )
    runtime_task = asyncio.create_task(
        runtime.run(), name=f"sandbox_inproc[{group}]"
    )

    try:
        # Yield until ``run()`` has entered and assigned the ``_ready``
        # event. ``create_task`` schedules but does not run; without
        # this poll the immediate ``wait_until_ready`` would see a None
        # ``_ready`` attribute and raise.
        loop = asyncio.get_event_loop()
        deadline = loop.time() + 5.0
        while not runtime.started and loop.time() < deadline:
            await asyncio.sleep(0)
        await runtime.wait_until_ready(timeout=10.0)
    except Exception:
        runtime_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await runtime_task
        raise

    # Pre-populate the manager so ``ensure_started`` finds a "running"
    # sandbox and skips the real subprocess spawn entirely. ``_sandboxes``
    # is the manager's internal map; accessing it from testing-side code
    # is the controlled minimum needed to inject our in-memory channel.
    process = _InProcessSandboxProcess(group, mgr_channel)
    manager._sandboxes[group] = process  # noqa: SLF001

    # Tests observe the bridge through main's block_till_done — teach it
    # to settle the whole sandbox round-trip first.
    _install_settling_block_till_done(hass, runtime, mgr_channel)

    # Mirror what the integration's ``_on_channel_ready`` does when the
    # real ``SandboxProcess`` opens its channel — register the bridge.
    data.bridges[group] = async_create_bridge(hass, group=group, channel=mgr_channel)
    mgr_channel.start()

    return InProcessSandbox(
        group=group, runtime=runtime, runtime_task=runtime_task, channel=mgr_channel
    )


def _one_shot_channel_factory(channel: Any):
    """Wrap a pre-built channel as a single-use ``ChannelFactory``."""
    used = False

    async def factory() -> Any:
        nonlocal used
        if used:
            raise RuntimeError("in-process SandboxRuntime asked for a second channel")
        used = True
        return channel

    return factory


@pytest_asyncio.fixture
async def sandbox_inprocess(
    hass: HomeAssistant,
    tmp_path_factory: pytest.TempPathFactory,
) -> AsyncIterator[InProcessSandbox]:
    """Set up the ``sandbox`` integration with an in-process built-in sandbox."""
    config_dir = tmp_path_factory.mktemp("sandbox_inproc")
    sandbox = await async_setup_inprocess_sandbox(
        hass, group=DEFAULT_GROUP, config_dir=str(config_dir)
    )
    try:
        yield sandbox
    finally:
        await sandbox.stop()


__all__ = [
    "DEFAULT_GROUP",
    "InProcessSandbox",
    "async_setup_inprocess_sandbox",
    "sandbox_inprocess",
]
