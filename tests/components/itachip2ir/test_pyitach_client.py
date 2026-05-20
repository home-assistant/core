"""Tests for iTach Client."""

import asyncio
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.itachip2ir.pyitach import (
    DEFAULT_PORT,
    ItachBusyError,
    ItachClient,
    ItachCommandError,
    ItachConnectionError,
    ItachResponseError,
    enabled_ir_ports,
    enabled_ir_ports_with_fallback,
    normalize_device_id,
    parse_device_line,
    parse_ir_response,
    parse_net_response,
)
import homeassistant.components.itachip2ir.pyitach._client as pyitach_client

HOST = "192.168.1.211"


class FakeWriter:
    """Fake stream writer."""

    def __init__(self) -> None:
        """Initialize fake writer."""
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        """Record written data."""
        self.writes.append(data)

    async def drain(self) -> None:
        """Drain fake writer."""

    def close(self) -> None:
        """Close fake writer."""
        self.closed = True

    def is_closing(self) -> bool:
        """Return whether fake writer is closing."""
        return self.closed

    async def wait_closed(self) -> None:
        """Wait for fake close."""


class FailingWriter(FakeWriter):
    """Fake writer that fails on write."""

    def write(self, data: bytes) -> None:
        """Raise write error."""
        raise OSError("write failed")


class FakeReader:
    """Fake stream reader."""

    def __init__(self, responses: list[bytes | Exception]) -> None:
        """Initialize fake reader."""
        self.responses = responses

    async def readuntil(self, separator: bytes = b"\r") -> bytes:
        """Return next fake response."""
        if not self.responses:
            raise asyncio.IncompleteReadError(partial=b"", expected=1)

        response = self.responses.pop(0)

        if isinstance(response, Exception):
            raise response

        return response


@pytest.mark.asyncio
async def test_async_connect_success() -> None:
    """Test successful TCP connection."""
    reader = FakeReader([])
    writer = FakeWriter()

    with patch(
        "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
        AsyncMock(return_value=(reader, writer)),
    ):
        client = ItachClient(HOST, DEFAULT_PORT)
        await client.async_connect()

    assert client._reader is cast(asyncio.StreamReader, reader)
    assert client._writer is cast(asyncio.StreamWriter, writer)


@pytest.mark.asyncio
async def test_async_connect_reuses_existing_connection() -> None:
    """Test async_connect does nothing when already connected."""

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([]))
    client._writer = cast(asyncio.StreamWriter, FakeWriter())
    with patch(
        "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
        AsyncMock(),
    ) as open_connection:
        await client.async_connect()

    open_connection.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_connect_failure() -> None:
    """Test TCP connection failure raises ItachConnectionError."""
    with patch(
        "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
        AsyncMock(side_effect=OSError("boom")),
    ):
        client = ItachClient(HOST, DEFAULT_PORT)

        with pytest.raises(ItachConnectionError):
            await client.async_connect()


@pytest.mark.asyncio
async def test_close_closes_writer() -> None:
    """Test close closes and clears writer."""
    reader = FakeReader([])
    writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, reader)
    client._writer = cast(asyncio.StreamWriter, writer)

    await client.close()

    assert writer.closed
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_close_ignores_wait_closed_oserror() -> None:
    """Test close ignores OSError from wait_closed."""

    class WaitClosedErrorWriter(FakeWriter):
        async def wait_closed(self) -> None:
            raise OSError("close failed")

    writer = WaitClosedErrorWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([]))
    client._writer = cast(asyncio.StreamWriter, writer)

    await client.close()

    assert writer.closed
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_read_response_line_requires_connection() -> None:
    """Test reading without connection raises connection error."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with pytest.raises(ItachConnectionError):
        await client._read_response_line()


@pytest.mark.asyncio
async def test_read_response_line_timeout_closes_connection() -> None:
    """Test response timeout closes connection."""
    writer = FakeWriter()
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([TimeoutError()]))
    client._writer = cast(asyncio.StreamWriter, writer)

    with pytest.raises(ItachConnectionError):
        await client._read_response_line()

    assert writer.closed
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_read_response_line_incomplete_read_closes_connection() -> None:
    """Test incomplete response closes connection."""
    writer = FakeWriter()
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(
        asyncio.StreamReader, FakeReader([asyncio.IncompleteReadError(b"", 1)])
    )
    client._writer = cast(asyncio.StreamWriter, writer)

    with pytest.raises(ItachConnectionError):
        await client._read_response_line()

    assert writer.closed
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_read_response_line_oserror_closes_connection() -> None:
    """Test socket read error closes connection."""
    writer = FakeWriter()
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([OSError("read failed")]))
    client._writer = cast(asyncio.StreamWriter, writer)

    with pytest.raises(ItachConnectionError):
        await client._read_response_line()

    assert writer.closed
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_send_command_success() -> None:
    """Test sending a raw command succeeds."""
    reader = FakeReader([b"OK\r"])
    writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, reader)
    client._writer = cast(asyncio.StreamWriter, writer)

    result = await client.send_command("test\r")

    assert result == "OK"
    assert writer.writes == [b"test\r"]


@pytest.mark.asyncio
async def test_send_command_does_not_retry_after_read_failure() -> None:
    """Test raw command is not retried after the write succeeds."""
    first_reader = FakeReader([asyncio.IncompleteReadError(b"", 1)])
    first_writer = FakeWriter()
    second_reader = FakeReader([b"OK\r"])
    second_writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, first_reader)
    client._writer = cast(asyncio.StreamWriter, first_writer)

    with (
        patch(
            "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
            AsyncMock(return_value=(second_reader, second_writer)),
        ),
        pytest.raises(ItachConnectionError),
    ):
        await client.send_command("test\r")

    assert first_writer.closed
    assert first_writer.writes == [b"test\r"]
    assert second_writer.writes == []


@pytest.mark.asyncio
async def test_send_command_does_not_retry_after_write_failure() -> None:
    """Test raw command is not retried after a write failure.

    A stream write/drain failure can happen after bytes have reached the
    device, so retrying may duplicate side effects.
    """
    first_reader = FakeReader([])
    first_writer = FailingWriter()
    second_reader = FakeReader([b"OK\r"])
    second_writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, first_reader)
    client._writer = cast(asyncio.StreamWriter, first_writer)

    with (
        patch(
            "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
            AsyncMock(return_value=(second_reader, second_writer)),
        ) as open_connection,
        pytest.raises(ItachConnectionError),
    ):
        await client.send_command("test\r")

    open_connection.assert_not_awaited()
    assert first_writer.closed
    assert second_writer.writes == []


@pytest.mark.asyncio
async def test_send_command_connection_not_open_after_connect() -> None:
    """Test command fails if writer is missing after connect."""
    client = ItachClient(HOST, DEFAULT_PORT)

    async def fake_connect() -> None:
        client._reader = cast(asyncio.StreamReader, FakeReader([]))
        client._writer = None

    with (
        patch.object(client, "async_connect", fake_connect),
        pytest.raises(ItachConnectionError),
    ):
        await client._send_command_locked("test\r")


@pytest.mark.asyncio
async def test_async_get_version_success() -> None:
    """Test getversion command."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with patch.object(
        client,
        "send_command",
        AsyncMock(return_value="710-1000-23"),
    ) as send:
        assert await client.async_get_version(1) == "710-1000-23"

    send.assert_awaited_once_with("getversion,1\r")


@pytest.mark.asyncio
async def test_async_get_version_error() -> None:
    """Test getversion error response."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with (
        patch.object(
            client,
            "send_command",
            AsyncMock(return_value="ERR_01"),
        ),
        pytest.raises(ItachCommandError),
    ):
        await client.async_get_version(1)


@pytest.mark.asyncio
async def test_async_get_net_success() -> None:
    """Test get_NET command."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with patch.object(
        client,
        "send_command",
        AsyncMock(return_value="NET,0:1,OK"),
    ) as send:
        assert await client.async_get_net() == "NET,0:1,OK"

    send.assert_awaited_once_with("get_NET,0:1\r")


@pytest.mark.asyncio
async def test_async_get_net_error() -> None:
    """Test get_NET error response."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with (
        patch.object(
            client,
            "send_command",
            AsyncMock(return_value="ERR_01"),
        ),
        pytest.raises(ItachCommandError),
    ):
        await client.async_get_net()


@pytest.mark.asyncio
async def test_get_devices_parses_valid_response() -> None:
    """Test getdevices response parsing."""
    reader = FakeReader(
        [
            b"device,0,0 WIFI\r",
            b"device,1,3 IR\r",
            b"device,2,1 SENSOR\r",
            b"endlistdevices\r",
        ]
    )
    writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, reader)
    client._writer = cast(asyncio.StreamWriter, writer)

    devices = await client.async_get_devices()

    assert devices == [
        "device,0,0 WIFI",
        "device,1,3 IR",
        "device,2,1 SENSOR",
    ]
    assert writer.writes == [b"getdevices\r"]


@pytest.mark.asyncio
async def test_get_devices_handles_endlist_on_same_line() -> None:
    """Test getdevices handles endlistdevices appended to a line."""
    reader = FakeReader([b"device,1,3 IR endlistdevices\r"])
    writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, reader)
    client._writer = cast(asyncio.StreamWriter, writer)

    assert await client.async_get_devices() == ["device,1,3 IR"]


@pytest.mark.asyncio
async def test_get_devices_error_response() -> None:
    """Test getdevices error response raises ItachCommandError."""
    reader = FakeReader([b"ERR_01\r"])
    writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, reader)
    client._writer = cast(asyncio.StreamWriter, writer)

    with pytest.raises(ItachCommandError):
        await client.async_get_devices()


@pytest.mark.asyncio
async def test_get_devices_does_not_retry_after_read_failure() -> None:
    """Test getdevices is not retried after the request was written."""
    first_reader = FakeReader([asyncio.IncompleteReadError(b"", 1)])
    first_writer = FakeWriter()
    second_reader = FakeReader([b"device,1,3 IR\r", b"endlistdevices\r"])
    second_writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, first_reader)
    client._writer = cast(asyncio.StreamWriter, first_writer)

    with (
        patch(
            "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
            AsyncMock(return_value=(second_reader, second_writer)),
        ) as open_connection,
        pytest.raises(ItachConnectionError),
    ):
        await client.async_get_devices()

    open_connection.assert_not_awaited()
    assert first_writer.closed
    assert first_writer.writes == [b"getdevices\r"]
    assert second_writer.writes == []


@pytest.mark.asyncio
async def test_get_ir_module_success() -> None:
    """Test IR module discovery."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with patch.object(
        client,
        "async_get_devices",
        AsyncMock(
            return_value=[
                "device,0,0 WIFI",
                "device,1,3 IR",
            ]
        ),
    ):
        assert await client.async_get_ir_module() == (1, 3)


@pytest.mark.asyncio
async def test_get_ir_module_skips_malformed_lines() -> None:
    """Test IR module discovery skips malformed device lines."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with patch.object(
        client,
        "async_get_devices",
        AsyncMock(
            return_value=[
                "",
                "badline",
                "device,wrong IR",
                "device,2,1 SENSOR",
                "device,1,3 IR",
            ]
        ),
    ):
        assert await client.async_get_ir_module() == (1, 3)


@pytest.mark.asyncio
async def test_get_ir_module_no_ir_module() -> None:
    """Test no IR module raises ItachCommandError."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with (
        patch.object(
            client,
            "async_get_devices",
            AsyncMock(return_value=["device,0,0 WIFI"]),
        ),
        pytest.raises(ItachCommandError),
    ):
        await client.async_get_ir_module()


@pytest.mark.asyncio
async def test_get_ir_connector_modes_parses_response() -> None:
    """Test get_IR connector mode parsing."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with patch.object(
        client,
        "send_command",
        AsyncMock(
            side_effect=[
                "IR,1:1,IR",
                "IR,1:2,SENSOR",
                "IR,1:3,IR_BLASTER",
            ]
        ),
    ) as send:
        result = await client.async_get_ir_connector_modes(1, 3)

    assert result == {
        1: "IR",
        2: "SENSOR",
        3: "IR_BLASTER",
    }
    assert send.await_args_list[0].args == ("get_IR,1:1\r",)
    assert send.await_args_list[1].args == ("get_IR,1:2\r",)
    assert send.await_args_list[2].args == ("get_IR,1:3\r",)


@pytest.mark.asyncio
async def test_get_ir_connector_modes_skips_error_and_malformed_response() -> None:
    """Test get_IR skips errors and malformed responses."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with patch.object(
        client,
        "send_command",
        AsyncMock(
            side_effect=[
                "ERR_01",
                "malformed",
                "IR,1:3,IR_BLASTER",
            ]
        ),
    ):
        result = await client.async_get_ir_connector_modes(1, 3)

    assert result == {
        3: "IR_BLASTER",
    }


@pytest.mark.asyncio
async def test_send_ir_success() -> None:
    """Test sendir success."""
    reader = FakeReader([b"completeir,1:1,1\r"])
    writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, reader)
    client._writer = cast(asyncio.StreamWriter, writer)

    await client.async_send_ir(1, 1, 38_000, [342, 171])

    assert writer.writes == [b"sendir,1:1,1,38000,1,1,342,171\r"]
    assert not writer.closed


@pytest.mark.asyncio
async def test_send_ir_default_command_id_when_none() -> None:
    """Test sendir uses default command ID when None is supplied."""
    reader = FakeReader([b"completeir,1:1,1\r"])
    writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, reader)
    client._writer = cast(asyncio.StreamWriter, writer)

    await client.async_send_ir(
        1,
        1,
        38_000,
        [342, 171],
        command_id=None,
    )

    assert writer.writes == [b"sendir,1:1,1,38000,1,1,342,171\r"]
    assert not writer.closed


@pytest.mark.asyncio
async def test_send_ir_reuses_fresh_connection() -> None:
    """Test sendir keeps a fresh TCP connection open for reuse."""
    reader = FakeReader([b"completeir,1:1,1\r", b"completeir,1:1,2\r"])
    writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, reader)
    client._writer = cast(asyncio.StreamWriter, writer)

    await client.async_send_ir(1, 1, 38_000, [342, 171], command_id=1)
    await client.async_send_ir(1, 1, 38_000, [342, 171], command_id=2)

    assert not writer.closed
    assert writer.writes == [
        b"sendir,1:1,1,38000,1,1,342,171\r",
        b"sendir,1:1,2,38000,1,1,342,171\r",
    ]


@pytest.mark.asyncio
async def test_send_ir_closes_idle_connection_before_reuse() -> None:
    """Test sendir closes an idle TCP connection before reuse."""
    first_reader = FakeReader([])
    first_writer = FakeWriter()
    second_reader = FakeReader([b"completeir,1:1,1\r"])
    second_writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, first_reader)
    client._writer = cast(asyncio.StreamWriter, first_writer)
    client._last_used_monotonic = 1.0

    with (
        patch(
            "homeassistant.components.itachip2ir.pyitach._client.time.monotonic",
            return_value=30.0,
        ),
        patch(
            "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
            AsyncMock(return_value=(second_reader, second_writer)),
        ),
    ):
        await client.async_send_ir(1, 1, 38_000, [342, 171], command_id=1)

    assert first_writer.closed
    assert second_writer.writes == [b"sendir,1:1,1,38000,1,1,342,171\r"]


@pytest.mark.asyncio
async def test_send_ir_does_not_retry_after_write_failure() -> None:
    """Test sendir is not retried after a socket write failure."""
    first_reader = FakeReader([])
    first_writer = FailingWriter()
    second_reader = FakeReader([b"completeir,1:1,1\r"])
    second_writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, first_reader)
    client._writer = cast(asyncio.StreamWriter, first_writer)

    with (
        patch(
            "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
            AsyncMock(return_value=(second_reader, second_writer)),
        ),
        pytest.raises(ItachConnectionError),
    ):
        await client.async_send_ir(1, 1, 38_000, [342, 171], command_id=1)

    assert first_writer.closed
    assert second_writer.writes == []


@pytest.mark.asyncio
async def test_send_ir_does_not_retry_after_response_read_failure() -> None:
    """Test sendir does not retry after write succeeded and response read failed."""
    first_reader = FakeReader([asyncio.IncompleteReadError(b"", 1)])
    first_writer = FakeWriter()
    second_reader = FakeReader([b"completeir,1:1,1\r"])
    second_writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, first_reader)
    client._writer = cast(asyncio.StreamWriter, first_writer)

    with (
        patch(
            "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
            AsyncMock(return_value=(second_reader, second_writer)),
        ),
        pytest.raises(ItachConnectionError),
    ):
        await client.async_send_ir(1, 1, 38_000, [342, 171], command_id=1)

    assert first_writer.closed
    assert first_writer.writes == [b"sendir,1:1,1,38000,1,1,342,171\r"]
    assert second_writer.writes == []


@pytest.mark.asyncio
async def test_send_ir_busy_response() -> None:
    """Test busy response raises ItachBusyError."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([b"busyIR,1:1,1\r"]))
    client._writer = cast(asyncio.StreamWriter, FakeWriter())

    with pytest.raises(ItachBusyError):
        await client.async_send_ir(1, 1, 38_000, [342, 171])


@pytest.mark.asyncio
async def test_send_ir_rejected_response() -> None:
    """Test ERR sendir response raises ItachCommandError."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([b"ERR_1:1,1\r"]))
    client._writer = cast(asyncio.StreamWriter, FakeWriter())

    with pytest.raises(ItachCommandError):
        await client.async_send_ir(1, 1, 38_000, [342, 171])


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"module": 0}, "Module must be >= 1"),
        ({"connector": 0}, "Connector must be >= 1"),
        ({"command_id": -1}, "Command ID must be between 0 and 65535"),
        ({"command_id": 65536}, "Command ID must be between 0 and 65535"),
        ({"carrier_frequency": 14_999}, "Carrier frequency"),
        ({"carrier_frequency": 500_001}, "Carrier frequency"),
        ({"repeat": 0}, "Repeat must be between 1 and 50"),
        ({"repeat": 51}, "Repeat must be between 1 and 50"),
        ({"offset": 0}, "Offset must be a positive odd number"),
        ({"offset": 2}, "Offset must be a positive odd number"),
        ({"timings": []}, "Timings list cannot be empty"),
        ({"timings": [1]}, "Timings list must contain on/off pairs"),
        ({"timings": [1, 0]}, "All timing values must be > 0"),
    ],
)
def test_validate_sendir_args(kwargs: dict[str, int | list[int]], match: str) -> None:
    """Test sendir validation failures."""
    client = ItachClient(HOST, DEFAULT_PORT)

    valid: dict[str, int | list[int]] = {
        "module": 1,
        "connector": 1,
        "carrier_frequency": 38_000,
        "timings": [342, 171],
        "repeat": 1,
        "offset": 1,
        "command_id": 1,
    }
    valid.update(kwargs)

    with pytest.raises(ValueError, match=match):
        client._validate_sendir_args(
            module=cast(int, valid["module"]),
            connector=cast(int, valid["connector"]),
            carrier_frequency=cast(int, valid["carrier_frequency"]),
            timings=cast(list[int], valid["timings"]),
            repeat=cast(int, valid["repeat"]),
            offset=cast(int, valid["offset"]),
            command_id=cast(int, valid["command_id"]),
        )


@pytest.mark.asyncio
async def test_send_command_does_not_retry_sendir_after_connection_error() -> None:
    """Test sendir commands are not retried after connection errors."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with (
        patch.object(
            client,
            "_send_command_locked",
            AsyncMock(side_effect=ItachConnectionError("boom")),
        ) as send,
        pytest.raises(ItachConnectionError),
    ):
        await client.send_command("sendir,1:1,1,38000,1,1,342,171\r")

    send.assert_awaited_once_with("sendir,1:1,1,38000,1,1,342,171\r")


def test_allocate_sendir_command_id_wraps() -> None:
    """Test sendir command ID wraps after 65535."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client._next_sendir_command_id = 65535

    assert client._allocate_sendir_command_id() == 65535
    assert client._next_sendir_command_id == 1


@pytest.mark.asyncio
async def test_async_get_net_malformed_response() -> None:
    """Test malformed get_NET response raises response error."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with (
        patch.object(client, "send_command", AsyncMock(return_value="bad")),
        pytest.raises(ItachResponseError),
    ):
        await client.async_get_net()


@pytest.mark.asyncio
async def test_async_get_net_info_parses_response() -> None:
    """Test parsed get_NET info."""
    client = ItachClient(HOST, DEFAULT_PORT)
    response = (
        "NET,0:1,192.168.1.211,255.255.255.0,"
        "192.168.1.1,1,8.8.8.8,00:0C:1E:12:34:56,extra"
    )

    with patch.object(client, "async_get_net", AsyncMock(return_value=response)):
        result = await client.async_get_net_info()

    assert result == {
        "raw": response,
        "address": "0:1",
        "ip_address": "192.168.1.211",
        "subnet_mask": "255.255.255.0",
        "gateway": "192.168.1.1",
        "dhcp_enabled": "1",
        "dns_server": "8.8.8.8",
        "mac_address": "00:0C:1E:12:34:56",
        "extra_fields": ["extra"],
    }


def test_parse_net_response_rejects_malformed() -> None:
    """Test malformed NET parser input raises response error."""
    with pytest.raises(ItachResponseError):
        parse_net_response("bad")


@pytest.mark.asyncio
async def test_get_multiline_writer_missing_after_connect() -> None:
    """Test multiline command fails if writer is missing after connect."""
    client = ItachClient(HOST, DEFAULT_PORT)

    async def fake_connect() -> None:
        client._reader = cast(asyncio.StreamReader, FakeReader([]))
        client._writer = None

    with (
        patch.object(client, "async_connect", fake_connect),
        pytest.raises(ItachConnectionError),
    ):
        await client._async_get_multiline_response_locked(
            command="getdevices\r",
            terminator="endlistdevices",
            response_lines=[],
        )


@pytest.mark.asyncio
async def test_get_devices_does_not_retry_after_write_failure() -> None:
    """Test getdevices is not retried after a write failure."""
    first_reader = FakeReader([])
    first_writer = FailingWriter()
    second_reader = FakeReader([b"endlistdevices\r"])
    second_writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, first_reader)
    client._writer = cast(asyncio.StreamWriter, first_writer)

    with (
        patch(
            "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
            AsyncMock(return_value=(second_reader, second_writer)),
        ) as open_connection,
        pytest.raises(ItachConnectionError),
    ):
        await client.async_get_devices()

    open_connection.assert_not_awaited()
    assert first_writer.closed
    assert second_writer.writes == []


@pytest.mark.asyncio
async def test_get_devices_missing_terminator() -> None:
    """Test missing multiline terminator raises response error."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([b"device,1,3 IR\r"] * 128))
    client._writer = cast(asyncio.StreamWriter, FakeWriter())

    with pytest.raises(ItachResponseError):
        await client.async_get_devices()


def test_parse_device_line_rejects_invalid_numbers_and_negative_values() -> None:
    """Test getdevices parser rejects invalid numeric values."""
    assert parse_device_line("device,x,3 IR") is None
    assert parse_device_line("device,1,x IR") is None
    assert parse_device_line("device,-1,3 IR") is None
    assert parse_device_line("device,1,-3 IR") is None


@pytest.mark.asyncio
async def test_get_ir_connector_modes_rejects_invalid_arguments() -> None:
    """Test get_IR connector mode argument validation."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with pytest.raises(ValueError, match="Module must be >= 1"):
        await client.async_get_ir_connector_modes(0, 3)

    with pytest.raises(ValueError, match="Ports must be >= 1"):
        await client.async_get_ir_connector_modes(1, 0)


@pytest.mark.asyncio
async def test_get_ir_connector_modes_ignores_wrong_connector_response() -> None:
    """Test get_IR ignores responses for unexpected connector."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with patch.object(client, "send_command", AsyncMock(return_value="IR,1:2,IR")):
        assert await client.async_get_ir_connector_modes(1, 1) == {}


def test_parse_ir_response_rejects_malformed_values() -> None:
    """Test get_IR parser rejects malformed responses."""
    assert parse_ir_response("bad") is None
    assert parse_ir_response("IR,1,IR") is None
    assert parse_ir_response("IR,x:1,IR") is None
    assert parse_ir_response("IR,1:x,IR") is None
    assert parse_ir_response("IR,1:1,") is None


@pytest.mark.asyncio
async def test_send_ir_ignores_stale_completeir_until_matching_response() -> None:
    """Test sendir ignores stale completeir responses."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(
        asyncio.StreamReader,
        FakeReader([b"completeir,1:1,999\r", b"completeir,1:1,1\r"]),
    )
    client._writer = cast(asyncio.StreamWriter, FakeWriter())

    await client.async_send_ir(1, 1, 38_000, [342, 171], command_id=1)


@pytest.mark.asyncio
async def test_send_ir_accepts_completeir_with_whitespace_extra_fields_and_numeric_ids() -> (
    None
):
    """Test sendir accepts valid completeir responses with extra formatting."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(
        asyncio.StreamReader, FakeReader([b" completeir , 01:001 , 0001 ,extra\r"])
    )
    client._writer = cast(asyncio.StreamWriter, FakeWriter())

    await client.async_send_ir(1, 1, 38_000, [342, 171], command_id=1)


@pytest.mark.asyncio
async def test_send_ir_unexpected_response_raises_command_error() -> None:
    """Test unexpected sendir response raises command error."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([b"unknown\r"]))
    client._writer = cast(asyncio.StreamWriter, FakeWriter())

    with pytest.raises(ItachCommandError):
        await client.async_send_ir(1, 1, 38_000, [342, 171])


@pytest.mark.asyncio
async def test_send_ir_missing_matching_completeir_raises_response_error() -> None:
    """Test sendir raises if matching completeir is never received."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(
        asyncio.StreamReader, FakeReader([b"completeir,1:1,999\r"] * 10)
    )
    client._writer = cast(asyncio.StreamWriter, FakeWriter())

    with pytest.raises(ItachResponseError):
        await client.async_send_ir(1, 1, 38_000, [342, 171], command_id=1)


@pytest.mark.asyncio
async def test_close_handles_writer_without_wait_closed() -> None:
    """Test close supports stream-like writers without wait_closed."""

    class NoWaitClosedWriter(FakeWriter):
        wait_closed = None  # type: ignore[assignment]

    writer = NoWaitClosedWriter()
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([]))
    client._writer = cast(asyncio.StreamWriter, writer)

    await client.close()

    assert writer.closed
    assert client._reader is None
    assert client._writer is None


@pytest.mark.asyncio
async def test_send_ir_rejects_negative_completeir_fields() -> None:
    """Test sendir ignores invalid completeir responses with negative fields."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(
        asyncio.StreamReader,
        FakeReader(
            [
                b"completeir,-1:1,1\r",
                b"completeir,1:-1,1\r",
                b"completeir,1:1,-1\r",
            ]
        ),
    )
    client._writer = cast(asyncio.StreamWriter, FakeWriter())

    with pytest.raises(ItachResponseError):
        await client.async_send_ir(1, 1, 38_000, [342, 171], command_id=1)


def test_enabled_ir_ports_filters_ir_output_modes() -> None:
    """Test connector mode filtering keeps only IR output-capable connectors."""
    assert enabled_ir_ports({1: "IR", 2: "SENSOR", 3: "IR_BLASTER"}, 3) == [1, 3]


def test_enabled_ir_ports_falls_back_when_modes_unavailable() -> None:
    """Test older firmware fallback treats reported connectors as IR-capable."""
    assert enabled_ir_ports({}, 3) == [1, 2, 3]


def test_enabled_ir_ports_with_fallback_serializes_modes() -> None:
    """Test capability helper returns serializable connector mode metadata."""
    assert enabled_ir_ports_with_fallback({1: "SENSOR", 2: "IR"}, 2) == (
        [2],
        {"1": "SENSOR", "2": "IR"},
    )


def test_enabled_ir_ports_with_fallback_reports_no_ir_when_modes_known() -> None:
    """Test known non-IR modes do not fall back to all ports."""
    assert enabled_ir_ports_with_fallback({1: "SENSOR"}, 1) == ([], {"1": "SENSOR"})


def test_enabled_ir_ports_with_fallback_marks_unknown_modes() -> None:
    """Test missing mode data falls back and marks modes as unknown."""
    assert enabled_ir_ports_with_fallback({}, 2) == (
        [1, 2],
        {"1": "UNKNOWN", "2": "UNKNOWN"},
    )


def test_normalize_device_id_returns_none_for_blank_values() -> None:
    """Test blank device identifiers are ignored."""
    assert normalize_device_id(None) is None
    assert normalize_device_id("   ") is None


@pytest.mark.asyncio
async def test_client_async_context_manager_connects_and_closes() -> None:
    """Test async context manager opens and closes the client."""
    client = ItachClient(HOST, DEFAULT_PORT)

    with (
        patch.object(client, "async_connect", AsyncMock()) as connect,
        patch.object(client, "close", AsyncMock()) as close,
    ):
        async with client as context_client:
            assert context_client is client

    connect.assert_awaited_once()
    close.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_connect_closes_partial_stale_connection_before_reconnect() -> None:
    """Test async_connect closes partial cached streams before reconnecting."""
    old_writer = FakeWriter()
    new_reader = FakeReader([])
    new_writer = FakeWriter()

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([]))
    client._writer = cast(asyncio.StreamWriter, old_writer)
    old_writer.closed = True

    with patch(
        "homeassistant.components.itachip2ir.pyitach._client.asyncio.open_connection",
        AsyncMock(return_value=(new_reader, new_writer)),
    ):
        await client.async_connect()

    assert client._reader is cast(asyncio.StreamReader, new_reader)
    assert client._writer is cast(asyncio.StreamWriter, new_writer)
    assert client._last_used_monotonic is None


def test_is_connected_returns_true_for_writer_without_is_closing() -> None:
    """Test connection check supports stream-like writers without is_closing."""

    class WriterWithoutIsClosing:
        """Minimal writer without is_closing."""

    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(asyncio.StreamReader, FakeReader([]))
    client._writer = cast(asyncio.StreamWriter, WriterWithoutIsClosing())

    assert client._is_connected() is True


@pytest.mark.asyncio
async def test_read_response_line_limit_overrun_closes_connection() -> None:
    """Test overlong response lines close the connection."""
    writer = FakeWriter()
    client = ItachClient(HOST, DEFAULT_PORT)
    client._reader = cast(
        asyncio.StreamReader,
        FakeReader([asyncio.LimitOverrunError("line too long", consumed=123)]),
    )
    client._writer = cast(asyncio.StreamWriter, writer)

    with pytest.raises(ItachConnectionError, match="exceeded buffer limit"):
        await client._read_response_line()

    assert writer.closed
    assert client._reader is None
    assert client._writer is None


def test_validate_sendir_args_rejects_connector_above_max_connector() -> None:
    """Test max connector validation rejects out-of-range connector."""
    client = ItachClient(HOST, DEFAULT_PORT)
    client.max_connector = 1

    with pytest.raises(ValueError, match="Connector must be between 1 and 1"):
        client._validate_sendir_args(
            module=1,
            connector=2,
            carrier_frequency=38_000,
            timings=[342, 171],
            repeat=1,
            offset=1,
            command_id=1,
        )


def test_parse_completeir_response_rejects_malformed_address_and_numbers() -> None:
    """Test completeir parser rejects malformed address and numeric fields."""
    assert pyitach_client._parse_completeir_response("completeir,1,1") is None
    assert pyitach_client._parse_completeir_response("completeir,x:1,1") is None
    assert pyitach_client._parse_completeir_response("completeir,1:x,1") is None
    assert pyitach_client._parse_completeir_response("completeir,1:1,x") is None


def test_completeir_matches_rejects_invalid_expected_response() -> None:
    """Test completeir matcher rejects malformed expected responses."""
    assert (
        pyitach_client._completeir_matches("completeir,1:1,1", "not-completeir")
        is False
    )
