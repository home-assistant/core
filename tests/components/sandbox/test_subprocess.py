"""End-to-end subprocess tests."""

import asyncio
import sys

import pytest

from homeassistant.components.sandbox.manager import SandboxConfig, SandboxManager
from homeassistant.core import HomeAssistant

FAST_CONFIG = SandboxConfig(
    restart_limit=2,
    restart_window=30.0,
    restart_backoff=0.05,
    ready_timeout=20.0,
    shutdown_grace=5.0,
)


@pytest.fixture(name="manager")
async def _manager_fixture(hass: HomeAssistant):
    """Manager + tighter timings; tears every sandbox down on exit."""

    def _factory(group: str, url: str) -> list[str]:
        return [
            sys.executable,
            "-m",
            "hass_client.sandbox",
            "--name",
            group,
            "--url",
            url,
        ]

    mgr = SandboxManager(hass, command_factory=_factory, config=FAST_CONFIG)
    yield mgr
    await mgr.async_stop_all()


async def test_subprocess_handshake_and_ping(manager: SandboxManager) -> None:
    """Spawn the runtime; channel comes up; ping round-trips; we tear down."""
    sandbox = await manager.ensure_started("built-in")
    assert sandbox.state == "running"
    channel = sandbox.channel
    assert channel is not None

    result = await asyncio.wait_for(channel.call("sandbox/ping", None), timeout=5.0)
    assert result.pong == "sandbox"

    await manager.async_stop("built-in")
    assert sandbox.state == "stopped"
