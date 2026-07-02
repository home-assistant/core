"""Tests for the Besen BS20 BLE client."""

from collections.abc import Callable
import logging
from typing import Any, cast

from besen_bs20 import client as client_module
from besen_bs20.client import BesenBS20Client
from besen_bs20.const import (
    NEW_BOARD_READ_UUID,
    NEW_BOARD_SERVICE_PREFIXES,
    NEW_BOARD_WRITE_UUID,
    READ_UUID,
    REV_BOARD_SERVICE_PREFIXES,
    REV_READ_UUID,
    REV_WRITE_UUID,
    WRITE_UUID,
)
from besen_bs20.exceptions import (
    CannotConnect,
    CommandFailed,
    InvalidAuth,
    ProtocolError,
)
from besen_bs20.models import BoardRevision, CharacteristicPair
from besen_bs20.protocol import PARSERS, build_command
from bleak.backends.device import BLEDevice
import pytest


class _Service:
    """Fake BLE service."""

    def __init__(self, uuid: str) -> None:
        """Initialize the service."""

        self.uuid = uuid


class _BleDevice:
    """Fake BLE device."""


class _FakeBleakClient:
    """Fake bleak client that emits a login flow."""

    def __init__(
        self,
        packets: list[bytes],
        *,
        service_uuid: str | None = None,
    ) -> None:
        """Initialize the fake client."""

        self.is_connected = True
        self.services = [
            _Service(service_uuid or "0000fff0-0000-1000-8000-00805f9b34fb")
        ]
        self.packets = packets
        self.writes: list[tuple[str, bytes, bool]] = []
        self.stopped_notifications: list[str] = []
        self.disconnected = False
        self.fail_write = False

    async def start_notify(
        self,
        uuid: str,
        callback: Callable[[int, bytearray], None],
    ) -> None:
        """Start notifications and replay queued packets."""

        for packet in self.packets:
            callback(1, bytearray(packet))

    async def stop_notify(self, uuid: str) -> None:
        """Record stopped notifications."""

        self.stopped_notifications.append(uuid)

    async def disconnect(self) -> None:
        """Disconnect the fake client."""

        self.disconnected = True
        self.is_connected = False

    async def write_gatt_char(
        self,
        uuid: str,
        data: bytes,
        *,
        response: bool,
    ) -> None:
        """Record GATT writes."""

        if self.fail_write:
            raise OSError("write failed")
        self.writes.append((uuid, data, response))


def _login_data() -> list[int]:
    """Return a valid login payload."""

    data = bytearray(69)
    data[0] = 10
    data[1:16] = b"Besen\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    data[17:32] = b"BS20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    data[33:49] = b"HW1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    data[49:53] = bytes([0, 0, 0, 22])
    data[53] = 32
    data[54:69] = b"basic\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    return list(data)


def _login_packets() -> list[bytes]:
    """Return packets for a successful login flow."""

    return [
        build_command(12345678, "123456", 1, _login_data()),
        build_command(12345678, "123456", 2, _login_data()),
    ]


def _client(
    fake_client: _FakeBleakClient,
    monkeypatch: pytest.MonkeyPatch,
) -> BesenBS20Client:
    """Create a client wired to fake BLE dependencies."""

    async def _establish_connection(*args: Any, **kwargs: Any) -> _FakeBleakClient:
        return fake_client

    monkeypatch.setattr(client_module, "establish_connection", _establish_connection)
    return BesenBS20Client(
        address="AA:BB:CC:DD:EE:FF",
        pin="123456",
        ble_device_provider=lambda: cast(BLEDevice, _BleDevice()),
        logger=logging.getLogger(__name__),
        advertised_name="ACP#Garage",
    )


@pytest.mark.asyncio
async def test_client_login_selects_new_board_characteristics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful login marks the client ready and selects new board UUIDs."""

    fake_bleak = _FakeBleakClient(
        _login_packets(),
        service_uuid=f"{NEW_BOARD_SERVICE_PREFIXES[0]}0000-1000-8000-00805f9b34fb",
    )
    client = _client(fake_bleak, monkeypatch)

    await client.async_start()
    await client.async_set_charge_amps(16)
    await client.async_stop()

    assert client.state.info.manufacturer == "Besen"
    assert client.state.info.model == "BS20"
    assert client.state.info.board_revision == BoardRevision.NEW
    assert fake_bleak.writes
    assert {write[0] for write in fake_bleak.writes} == {NEW_BOARD_WRITE_UUID}
    assert fake_bleak.stopped_notifications == [NEW_BOARD_READ_UUID]
    assert fake_bleak.disconnected is True


@pytest.mark.asyncio
async def test_client_public_commands_and_listeners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Public command helpers send commands and listener removal works."""

    fake_bleak = _FakeBleakClient(_login_packets())
    client = _client(fake_bleak, monkeypatch)
    updates: list[bool] = []

    remove_listener = client.add_listener(lambda data: updates.append(data.available))

    await client.async_start()
    await client.async_start_charging()
    await client.async_stop_charging()
    await client.async_set_lcd_brightness(150)
    await client.async_set_temperature_unit("Fahrenheit")
    await client.async_set_language("Deutsch")
    await client.async_set_device_name("Garage")
    update_count = len(updates)
    remove_listener()
    client._set_state(available=True)

    with pytest.raises(CommandFailed, match="Unsupported temperature unit"):
        await client.async_set_temperature_unit("Kelvin")
    with pytest.raises(CommandFailed, match="Unsupported language"):
        await client.async_set_language("Klingon")
    with pytest.raises(CommandFailed, match="Device name cannot be empty"):
        await client.async_set_device_name("   ")

    assert updates
    assert len(updates) == update_count
    await client.async_stop()


@pytest.mark.asyncio
async def test_client_selects_revised_and_old_characteristics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Characteristic selection handles revised and old boards."""

    revised_fake = _FakeBleakClient(
        _login_packets(),
        service_uuid=f"{REV_BOARD_SERVICE_PREFIXES[0]}0000-1000-8000-00805f9b0131",
    )
    revised = _client(revised_fake, monkeypatch)
    await revised.async_start()
    await revised.async_stop()

    old_fake = _FakeBleakClient(_login_packets())
    old = _client(old_fake, monkeypatch)
    await old.async_start()
    await old.async_stop()

    assert revised.state.info.board_revision == BoardRevision.REVISED
    assert old.state.info.board_revision == BoardRevision.OLD
    assert revised_fake.stopped_notifications == [REV_READ_UUID]
    assert {write[0] for write in revised_fake.writes} == {REV_WRITE_UUID}
    assert {write[0] for write in old_fake.writes} == {WRITE_UUID}


@pytest.mark.asyncio
async def test_client_raises_invalid_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """A charger auth rejection raises InvalidAuth."""

    fake_bleak = _FakeBleakClient([build_command(12345678, "123456", 341)])
    client = _client(fake_bleak, monkeypatch)

    with pytest.raises(InvalidAuth):
        await client.async_start()

    assert client.state.authenticated is False
    await client.async_stop()


@pytest.mark.asyncio
async def test_client_raises_when_ble_device_missing() -> None:
    """Missing connectable Bluetooth devices fail before connecting."""

    client = BesenBS20Client(
        address="AA:BB:CC:DD:EE:FF",
        pin="123456",
        ble_device_provider=lambda: None,
        logger=logging.getLogger(__name__),
    )

    with pytest.raises(CannotConnect, match="No connectable Bluetooth path"):
        await client.async_start()


@pytest.mark.asyncio
async def test_client_marks_unavailable_when_write_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BLE write failures raise CommandFailed and mark the state unavailable."""

    fake_bleak = _FakeBleakClient(_login_packets())
    client = _client(fake_bleak, monkeypatch)
    await client.async_start()

    fake_bleak.fail_write = True

    with pytest.raises(CommandFailed, match="Failed to send set_output_amps"):
        await client.async_set_charge_amps(16)

    assert client.state.available is False
    assert client.state.last_error == "Failed to send set_output_amps: write failed"
    await client.async_stop()


@pytest.mark.asyncio
async def test_client_connect_timeout_and_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connection timeout and establish failures raise CannotConnect."""

    fake_bleak = _FakeBleakClient([])
    timeout_client = _client(fake_bleak, monkeypatch)
    monkeypatch.setattr(client_module, "LOGIN_TIMEOUT", 0.01)

    with pytest.raises(CannotConnect, match="Timed out"):
        await timeout_client.async_start()
    await timeout_client.async_stop()

    async def _fail_connect(*args: Any, **kwargs: Any) -> _FakeBleakClient:
        del args, kwargs
        raise OSError("no route")

    monkeypatch.setattr(client_module, "establish_connection", _fail_connect)
    failing_client = _client(fake_bleak, monkeypatch)
    monkeypatch.setattr(client_module, "establish_connection", _fail_connect)

    with pytest.raises(CannotConnect, match="Unable to connect"):
        await failing_client.async_start()


@pytest.mark.asyncio
async def test_client_packet_handler_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Packet handler updates state for command families."""

    fake_bleak = _FakeBleakClient(_login_packets())
    client = _client(fake_bleak, monkeypatch)
    await client.async_start()

    monkeypatch.setitem(PARSERS, 4, lambda data, ident: {"line_id": 1})
    monkeypatch.setitem(PARSERS, 257, lambda data, ident: {"rssi": -50})
    monkeypatch.setitem(
        PARSERS,
        262,
        lambda data, ident: {"hardware_version": "HW2"},
    )
    monkeypatch.setitem(
        PARSERS,
        7,
        lambda data, ident: {"error_reason": "Denied"},
    )
    monkeypatch.setitem(
        PARSERS,
        8,
        lambda data, ident: {"stop_result": "Card swiping stop"},
    )

    await client._async_handle_packet(3, b"", "")
    await client._async_handle_packet(4, b"", "")
    await client._async_handle_packet(257, b"", "")
    await client._async_handle_packet(262, b"", "")
    await client._async_handle_packet(7, b"", "")
    await client._async_handle_packet(8, b"", "")

    def _raise_parser(data: bytes, identifier: str) -> dict[str, Any]:
        del data, identifier
        raise ProtocolError("bad")

    monkeypatch.setitem(PARSERS, 999, _raise_parser)
    await client._async_handle_packet(999, b"", "")

    assert client.state.charge.line_id == 1
    assert client.state.config.rssi == -50
    assert client.state.info.hardware_version == "HW2"
    assert client.state.last_command is not None
    assert client.state.last_command.command == "charge_stop"
    await client.async_stop()


@pytest.mark.asyncio
async def test_client_disconnect_notification_and_send_preconditions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disconnect, malformed notifications, and send preconditions are handled."""

    fake_bleak = _FakeBleakClient(_login_packets())
    client = _client(fake_bleak, monkeypatch)
    await client.async_start()

    scheduled = False

    def _schedule_reconnect() -> None:
        nonlocal scheduled
        scheduled = True

    monkeypatch.setattr(client, "_schedule_reconnect", _schedule_reconnect)
    client._disconnected(cast(Any, fake_bleak))

    packet = bytearray(build_command(12345678, "123456", 32771, [1]))
    packet[10] ^= 0xFF
    client._notification(1, packet)

    assert scheduled is True
    assert client.state.available is False
    assert client.state.last_error == "Bluetooth connection lost"

    disconnected = BesenBS20Client(
        address="AA:BB:CC:DD:EE:FF",
        pin="123456",
        ble_device_provider=lambda: cast(BLEDevice, _BleDevice()),
        logger=logging.getLogger(__name__),
    )
    with pytest.raises(CommandFailed, match="not connected"):
        await disconnected._send_command(32770, None, name="login_request")

    disconnected._client = cast(Any, _FakeBleakClient([]))
    disconnected._characteristics = CharacteristicPair(
        read_uuid=READ_UUID,
        write_uuid=WRITE_UUID,
        board_revision=BoardRevision.OLD,
    )
    with pytest.raises(CommandFailed, match="serial is not known"):
        await disconnected._send_command(32770, None, name="login_request")

    client._set_state(info=client.state.info.updated(phases=1))
    assert client._charge_start_payload(6)[0] == 1
    client._update_info()
    client._set_state(
        info=client.state.info.updated(
            board_revision=BoardRevision.REVISED,
            software_version=None,
        )
    )
    client._update_info(hardware_version="fallback")
    assert client.state.info.hardware_version == "fallback"
    assert client.state.info.software_version == "fallback"
    await client.async_stop()
