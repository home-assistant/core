"""In-memory transport joining a manager-side and runtime-side Channel."""

import asyncio
from typing import Any

from hass_client.channel import Channel as ClientChannel


class _LoopbackWriter:
    """Async writer that pushes bytes straight into a paired StreamReader."""

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


def make_inproc_channel_pair(*, group: str) -> tuple[Any, ClientChannel]:
    """Return ``(manager_channel, runtime_channel)`` joined in-memory."""
    # Lazy import: the manager-side Channel lives in the HA integration
    # tree. Importing it eagerly would couple the testing helper to a
    # component that may not be loaded.
    from hass_client.codec_protobuf import ProtobufCodec as ClientCodec  # noqa: PLC0415
    from homeassistant.components.sandbox.channel import (  # noqa: PLC0415
        Channel as MgrChannel,
    )
    from homeassistant.components.sandbox.codec_protobuf import (  # noqa: PLC0415
        ProtobufCodec as MgrCodec,
    )

    reader_a = asyncio.StreamReader()
    reader_b = asyncio.StreamReader()
    # writer_a writes → reader_b feeds (runtime reads what manager wrote)
    # writer_b writes → reader_a feeds (manager reads what runtime wrote)
    writer_a = _LoopbackWriter(reader_b)
    writer_b = _LoopbackWriter(reader_a)
    # Each side builds its own ProtobufCodec from its own _proto mirror; the
    # wire is identical, so the two are fully interoperable.
    mgr_channel = MgrChannel(reader_a, writer_a, name=f"mgr:{group}", codec=MgrCodec())
    rt_channel = ClientChannel(
        reader_b, writer_b, name=f"rt:{group}", codec=ClientCodec()
    )
    return mgr_channel, rt_channel


__all__ = ["make_inproc_channel_pair"]
