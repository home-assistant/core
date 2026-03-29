"""Tests for the Aurora ABB PowerOne integration setup and migration."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.aurora_abb_powerone.const import (
    CONF_INVERTER_SERIAL_ADDRESS,
    CONF_SERIAL_COMPORT,
    CONF_TCP_HOST,
    CONF_TCP_PORT,
    CONF_TRANSPORT,
    DOMAIN,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant

from .conftest import MOCK_INVERTER_DATA
from .const import MOCK_FIRMWARE, MOCK_MODEL, MOCK_SERIAL_NUMBER

from tests.common import MockConfigEntry

MOCK_DATA_SERIAL = {
    CONF_TRANSPORT: TRANSPORT_SERIAL,
    CONF_INVERTER_SERIAL_ADDRESS: 3,
    CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
    ATTR_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
    "model": MOCK_MODEL,
    "firmware": MOCK_FIRMWARE,
}

MOCK_DATA_TCP = {
    CONF_TRANSPORT: TRANSPORT_TCP,
    CONF_INVERTER_SERIAL_ADDRESS: 3,
    CONF_TCP_HOST: "127.0.0.1",
    CONF_TCP_PORT: 502,
    ATTR_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
    "model": MOCK_MODEL,
    "firmware": MOCK_FIRMWARE,
}


@pytest.mark.parametrize(
    ("entry_data", "factory_method"),
    [
        (MOCK_DATA_SERIAL, "from_serial"),
        (MOCK_DATA_TCP, "from_tcp"),
    ],
)
async def test_setup_and_unload(
    hass: HomeAssistant,
    entry_data: dict,
    factory_method: str,
) -> None:
    """Test setup and unload for serial and TCP transports."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=entry_data,
        unique_id=MOCK_SERIAL_NUMBER,
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_client.try_connect_and_fetch_data.return_value = MOCK_INVERTER_DATA

    with patch(
        f"homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.{factory_method}",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_unsupported_transport(hass: HomeAssistant) -> None:
    """Test that setup raises ValueError for unsupported transport."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TRANSPORT: "unsupported",
            CONF_INVERTER_SERIAL_ADDRESS: 3,
            ATTR_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
            "model": MOCK_MODEL,
            "firmware": MOCK_FIRMWARE,
        },
        unique_id=MOCK_SERIAL_NUMBER,
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_migrate_entry_v1_to_v1_2(hass: HomeAssistant) -> None:
    """Test migration from config entry version 1.1 to 1.2."""
    old_data = {
        "port": "/dev/ttyUSB7",
        "address": 3,
        ATTR_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
        "model": MOCK_MODEL,
        "firmware": MOCK_FIRMWARE,
        "title": "PhotoVoltaic Inverters",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=old_data,
        unique_id=MOCK_SERIAL_NUMBER,
        version=1,
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_client.try_connect_and_fetch_data.return_value = MOCK_INVERTER_DATA

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data[CONF_TRANSPORT] == TRANSPORT_SERIAL
    assert entry.data[CONF_INVERTER_SERIAL_ADDRESS] == 3
    assert entry.data[CONF_SERIAL_COMPORT] == "/dev/ttyUSB7"
    # Old keys preserved
    assert entry.data["port"] == "/dev/ttyUSB7"
    assert entry.data["address"] == 3
    assert entry.state is ConfigEntryState.LOADED


async def test_migrate_entry_v1_to_v1_2_missing_legacy_keys(
    hass: HomeAssistant,
) -> None:
    """Test that migration fails gracefully when legacy keys are missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={ATTR_SERIAL_NUMBER: MOCK_SERIAL_NUMBER},
        unique_id=MOCK_SERIAL_NUMBER,
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migrate_entry_future_version(hass: HomeAssistant) -> None:
    """Test that migration fails for entries from future versions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TRANSPORT: TRANSPORT_SERIAL},
        unique_id=MOCK_SERIAL_NUMBER,
        version=99,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
