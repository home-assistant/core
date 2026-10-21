"""In-process pytest plugin for sandbox compat tests."""

import asyncio
from collections.abc import AsyncIterator, Callable
import contextlib
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

from hass_client.sandbox import SandboxRuntime
from hass_client.testing._autotag import (
    configure_compat_plugin,
    engagement_count,
    tagged_count,
)
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
    """Inject the in-process sandbox into every ``hass``-using test."""
    for item in items:
        fixtures = getattr(item, "fixturenames", None)
        if fixtures is None or "hass" not in fixtures:
            continue
        if "sandbox_inprocess" not in fixtures:
            fixtures.append("sandbox_inprocess")


def pytest_terminal_summary(
    terminalreporter: Any, exitstatus: int, config: pytest.Config
) -> None:
    """Report how often the sandbox router actually engaged."""
    terminalreporter.write_line(
        f"sandbox-compat: router entry_setup engaged {engagement_count()} time(s),"
        f" {tagged_count()} entries tagged"
    )


@dataclass
class InProcessSandbox:
    """Handle for one running in-process sandbox."""

    group: str
    runtime: SandboxRuntime
    runtime_task: asyncio.Task[int]
    channel: Any = None

    async def stop(self) -> None:
        """Gracefully shut the runtime down, then wait for the task."""
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
    """Stand-in for :class:`SandboxProcess` that wraps an in-memory channel."""

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
        from homeassistant.components.sandbox.messages import MSG_SHUTDOWN  # noqa: PLC0415

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
    """Make main's ``async_block_till_done`` settle the sandbox round-trip."""
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
    """Set up ``sandbox`` and run a sandbox runtime in-process."""
    # Lazy import to keep ``hass_client.testing`` import-time free of HA
    # integration code (the testing package may be imported even when
    # the integration isn't installed).
    from homeassistant.components.sandbox.bridge import async_create_bridge  # noqa: PLC0415
    from homeassistant.components.sandbox.const import DATA_SANDBOX  # noqa: PLC0415
    from homeassistant.setup import async_setup_component  # noqa: PLC0415

    assert await async_setup_component(hass, "sandbox", {})
    data = hass.data[DATA_SANDBOX]
    manager = data.manager
    if manager is None:  # pragma: no cover — defensive only
        raise RuntimeError("sandbox setup did not install a manager")

    mgr_channel, rt_channel = make_inproc_channel_pair(group=group)

    # Serve the worker's restore-state load before it can signal readiness.
    data.bridges[group] = async_create_bridge(hass, group=group, channel=mgr_channel)
    mgr_channel.start()

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
        # Wait until run() creates the readiness event before awaiting it.
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

    # Inject the in-memory worker so tests do not spawn a subprocess.
    process = _InProcessSandboxProcess(group, mgr_channel)
    manager._sandboxes[group] = process  # noqa: SLF001

    # Tests observe the bridge through main's block_till_done — teach it
    # to settle the whole sandbox round-trip first.
    _install_settling_block_till_done(hass, runtime, mgr_channel)

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
