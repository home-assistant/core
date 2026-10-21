"""Runtime-side transport selection + unix channel."""

import asyncio
import contextlib
from pathlib import Path
import tempfile

from homeassistant_sandbox.__main__ import _build_parser
from homeassistant_sandbox._proto import sandbox_pb2 as pb
from homeassistant_sandbox.channel import Channel
from homeassistant_sandbox.codec_protobuf import ProtobufCodec
from homeassistant_sandbox.runtime import (
    SandboxRuntime,
    _open_unix_channel,
    _transport_scheme,
)
import pytest


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("", "stdio"),
        ("stdio://", "stdio"),
        ("unix:///tmp/sandbox.sock", "unix"),
        ("ws://localhost:8123/api/websocket", "ws"),
        ("wss://example.test/ws", "ws"),
    ],
)
def test_transport_scheme_selection(url: str, expected: str) -> None:
    """Each ``--url`` maps to its transport kind."""
    assert _transport_scheme(url) == expected


def test_transport_scheme_rejects_unknown() -> None:
    """An unrecognised scheme raises rather than silently defaulting."""
    with pytest.raises(ValueError, match="unsupported sandbox transport url"):
        _transport_scheme("amqp://broker/queue")


def test_cli_url_defaults_to_stdio() -> None:
    """Omitting ``--url`` selects the stdio transport."""
    args = _build_parser().parse_args(["--name", "built-in"])
    assert args.url == "stdio://"


async def test_websocket_transport_rejected() -> None:
    """A ``ws://`` URL is rejected with a clear not-implemented error."""
    runtime = SandboxRuntime(url="ws://localhost:8123/api/websocket", group="g")
    with pytest.raises(NotImplementedError, match="not implemented in this build"):
        await runtime._default_channel_factory()  # noqa: SLF001


async def test_open_unix_channel_round_trips() -> None:
    """A call round-trips over a real unix socket via the runtime opener."""
    server_channels: list[Channel] = []

    async def _ping(_payload: object) -> pb.PingResult:
        return pb.PingResult(pong="pong-unix")

    def _on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        channel = Channel(reader, writer, name="server", codec=ProtobufCodec())
        channel.register("sandbox/ping", _ping)
        channel.start()
        server_channels.append(channel)

    with tempfile.TemporaryDirectory(prefix="sandbox_test_") as socket_dir:
        socket_path = str(Path(socket_dir) / "control.sock")
        server = await asyncio.start_unix_server(_on_connect, path=socket_path)
        client = await _open_unix_channel(socket_path, name="client")
        try:
            client.start()
            result = await asyncio.wait_for(
                client.call("sandbox/ping", None), timeout=5.0
            )
            assert result.pong == "pong-unix"
        finally:
            await client.close()
            for channel in server_channels:
                await channel.close()
            server.close()
            server.close_clients()
            with contextlib.suppress(Exception):
                await server.wait_closed()
