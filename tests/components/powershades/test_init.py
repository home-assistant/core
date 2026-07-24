"""Tests for setting up and unloading the PowerShades integration."""

import struct
from unittest.mock import AsyncMock, patch

from pyowershades import (
    OP_GET_SERIAL,
    OP_GET_STATUS,
    PowerShadesConnection,
    PowerShadesTimeoutError,
    build_packet,
)

from homeassistant.components.powershades.const import DOMAIN
from homeassistant.components.powershades.coordinator import PowerShadesCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_IP, TEST_NAME, TEST_SERIAL, status_packet

from tests.common import MockConfigEntry


async def test_setup_entry_success(hass: HomeAssistant, config_entry) -> None:
    """A working device sets up successfully with a coordinator and entities."""
    assert config_entry.state is ConfigEntryState.LOADED
    assert isinstance(config_entry.runtime_data, PowerShadesCoordinator)
    assert config_entry.runtime_data.data.position == 50

    assert len(hass.states.async_all("cover")) == 1


async def test_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """The entry retries setup if the device doesn't respond."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip": TEST_IP, "serial": TEST_SERIAL, "name": TEST_NAME, "model": 1},
        unique_id=str(TEST_SERIAL),
    )
    entry.add_to_hass(hass)

    async def fake_request(op, payload=b"", timeout=None, retries=None):
        raise PowerShadesTimeoutError("no reply")

    with (
        patch.object(PowerShadesConnection, "async_connect", AsyncMock()),
        patch.object(
            PowerShadesConnection,
            "async_request",
            AsyncMock(side_effect=fake_request),
        ),
        patch.object(PowerShadesConnection, "close") as mock_close,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_close.assert_called_once()


async def test_unload_entry(hass: HomeAssistant, config_entry) -> None:
    """Unloading the entry unloads platforms and closes the connection."""
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    cover_states = hass.states.async_all("cover")
    assert len(cover_states) == 1
    assert cover_states[0].state == "unavailable"

    PowerShadesConnection.close.assert_called_once()


async def test_setup_entry_fills_in_missing_model(hass: HomeAssistant) -> None:
    """A first-time setup with no stored model fills it in."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip": TEST_IP, "serial": TEST_SERIAL, "name": TEST_NAME},
        unique_id=str(TEST_SERIAL),
    )
    entry.add_to_hass(hass)

    # model, pad, pad, direction, serial low, serial high, dhcp_enabled
    serial_payload = struct.pack("<BBBBIIB", 1, 0, 0, 0, TEST_SERIAL, 0, 0)
    serial_payload += b"\x00" * (24 - 8 - len(serial_payload))
    serial_packet = build_packet(OP_GET_SERIAL, payload=serial_payload)

    async def fake_request(op, payload=b"", timeout=None, retries=None):
        if op == OP_GET_STATUS:
            return status_packet()
        if op == OP_GET_SERIAL:
            return serial_packet
        return build_packet(op)

    with (
        patch.object(PowerShadesConnection, "async_connect", AsyncMock()),
        patch.object(
            PowerShadesConnection,
            "async_request",
            AsyncMock(side_effect=fake_request),
        ),
        patch.object(PowerShadesConnection, "close"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.data["model"] == 1


async def test_setup_entry_serial_probe_timeout(hass: HomeAssistant) -> None:
    """A timeout probing for the model leaves it unset but setup still succeeds."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip": TEST_IP, "serial": TEST_SERIAL, "name": TEST_NAME},
        unique_id=str(TEST_SERIAL),
    )
    entry.add_to_hass(hass)

    async def fake_request(op, payload=b"", timeout=None, retries=None):
        if op == OP_GET_STATUS:
            return status_packet()
        if op == OP_GET_SERIAL:
            raise PowerShadesTimeoutError("no reply")
        return build_packet(op)

    with (
        patch.object(PowerShadesConnection, "async_connect", AsyncMock()),
        patch.object(
            PowerShadesConnection,
            "async_request",
            AsyncMock(side_effect=fake_request),
        ),
        patch.object(PowerShadesConnection, "close"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert "model" not in entry.data
