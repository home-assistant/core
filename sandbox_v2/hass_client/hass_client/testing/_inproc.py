"""In-memory transport joining a manager-side and runtime-side Channel.

Mirrors ``tests/components/sandbox_v2/_helpers.py:make_channel_pair`` so
the testing plugin can build channel pairs without importing from the
core tests tree (TID251 forbids ``hass_client`` → ``tests`` imports).

The duplication is intentional — keep both copies tiny and obviously
equivalent. If this helper grows, lift it to a shared utility.
"""

import asyncio
from typing import Any

from hass_client.channel import Channel as ClientChannel


class _LoopbackWriter:
    """Async writer that pushes bytes straight into a paired StreamReader.

    Implements the slice of :class:`asyncio.StreamWriter` that
    :class:`Channel` actually uses: ``write``, ``drain``, ``close``, and
    ``wait_closed``. Bytes written go straight into the paired reader's
    buffer, so the partner :class:`Channel` reads them on its next loop
    iteration with no socket or pipe involved.
    """

    def __init__(self, target: asyncio.StreamReader) -> None:
        """Wrap ``target`` so writes feed it directly."""
        self._target = target
        self._closed = False

    def write(self, data: bytes) -> None:
        """Push ``data`` into the paired reader."""
        if self._closed:
            return
        self._target.feed_data(data)

    async def drain(self) -> None:
        """No-op — the loopback transport is unbuffered."""

    def close(self) -> None:
        """Signal EOF to the paired reader."""
        if self._closed:
            return
        self._closed = True
        self._target.feed_eof()

    async def wait_closed(self) -> None:
        """No-op — :meth:`close` is synchronous for the loopback."""


def make_inproc_channel_pair(
    *, group: str
) -> tuple[Any, ClientChannel]:
    """Return ``(manager_channel, runtime_channel)`` joined in-memory.

    The manager-side channel is the one the HA integration's
    :class:`SandboxBridge` reads from; the runtime-side channel is what
    :class:`hass_client.sandbox.SandboxRuntime` consumes.

    The manager-side type is imported lazily because the testing package
    must not pull ``homeassistant.components.sandbox_v2`` at import time
    (the integration is not always installed when ``hass_client`` is
    used). The wire format is identical on both sides; the separate
    classes exist only to honour the project's import-boundary rule.
    """
    # Lazy import: the manager-side Channel lives in the HA integration
    # tree. Importing it eagerly would couple the testing helper to a
    # component that may not be loaded.
    from homeassistant.components.sandbox_v2.channel import (  # noqa: PLC0415
        Channel as MgrChannel,
    )

    reader_a = asyncio.StreamReader()
    reader_b = asyncio.StreamReader()
    # writer_a writes → reader_b feeds (runtime reads what manager wrote)
    # writer_b writes → reader_a feeds (manager reads what runtime wrote)
    writer_a = _LoopbackWriter(reader_b)
    writer_b = _LoopbackWriter(reader_a)
    mgr_channel = MgrChannel(reader_a, writer_a, name=f"mgr:{group}")
    rt_channel = ClientChannel(reader_b, writer_b, name=f"rt:{group}")
    return mgr_channel, rt_channel


__all__ = ["make_inproc_channel_pair"]
