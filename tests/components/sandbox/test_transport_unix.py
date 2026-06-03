"""Unix-socket control-channel transport (transport T3).

Spawns the real ``python -m hass_client.sandbox`` runtime with the
manager configured for the unix-socket transport: the manager opens a
listening unix socket, passes ``--url unix://<path>`` to the subprocess,
the runtime dials back, and a ``ping`` round-trips over the socket. Also
covers manager-side transport selection and socket cleanup on shutdown.
"""

import asyncio
import os
import sys

import pytest

from homeassistant.components.sandbox.manager import (
    TRANSPORT_UNIX,
    SandboxConfig,
    SandboxManager,
)
from homeassistant.core import HomeAssistant

FAST_CONFIG = SandboxConfig(
    restart_limit=2,
    restart_window=30.0,
    restart_backoff=0.05,
    ready_timeout=20.0,
    shutdown_grace=5.0,
)


def _runtime_factory(seen: dict[str, str]) -> object:
    """Command factory that records the URL the manager hands it."""

    def _factory(group: str, url: str) -> list[str]:
        seen["url"] = url
        return [
            sys.executable,
            "-m",
            "hass_client.sandbox",
            "--name",
            group,
            "--url",
            url,
            "--token",
            "t3-unix-token",
        ]

    return _factory


async def test_unix_socket_round_trip(hass: HomeAssistant) -> None:
    """Manager opens a unix socket; runtime connects; ping round-trips."""
    seen: dict[str, str] = {}
    mgr = SandboxManager(
        hass,
        command_factory=_runtime_factory(seen),
        config=FAST_CONFIG,
        transport=TRANSPORT_UNIX,
    )
    try:
        sandbox = await mgr.ensure_started("built-in")
        assert sandbox.state == "running"

        # The manager selected the unix transport and handed the runtime a
        # unix:// socket path that exists while the sandbox is running.
        assert seen["url"].startswith("unix://")
        socket_path = seen["url"].removeprefix("unix://")
        assert os.path.exists(socket_path)

        channel = sandbox.channel
        assert channel is not None
        result = await asyncio.wait_for(channel.call("sandbox/ping", None), timeout=5.0)
        assert result.pong == "sandbox"
    finally:
        await mgr.async_stop_all()

    assert sandbox.state == "stopped"

    # No leaked socket file or tempdir after shutdown.
    socket_path = seen["url"].removeprefix("unix://")
    assert not os.path.exists(socket_path)
    assert not os.path.exists(os.path.dirname(socket_path))


async def test_unknown_transport_rejected(hass: HomeAssistant) -> None:
    """An unknown transport name is rejected at construction time."""
    with pytest.raises(ValueError, match="unknown sandbox transport"):
        SandboxManager(hass, transport="carrier-pigeon")
