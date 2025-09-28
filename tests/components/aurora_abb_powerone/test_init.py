"""Pytest modules for Aurora ABB Powerone PV inverter sensor integration."""

from unittest.mock import patch

from homeassistant.components.aurora_abb_powerone import async_migrate_entry
from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
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

from tests.common import MockConfigEntry

CURRENT_VERSION = 2


async def test_migrate_entry_v1_to_v2_serial(hass: HomeAssistant) -> None:
    """Migrate a v1 entry (serial-only) to v2 with transport + renamed keys."""

    old_data = {
        "port": "/dev/ttyUSB0",
        "address": 2,
        "serial_number": "SN0001",
        "model": "PVI-3.0",
        "firmware": "1.2.3",
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Old Aurora",
        data=old_data,
        version=1,
        minor_version=0,
    )
    entry.add_to_hass(hass)

    ok = await async_migrate_entry(hass, entry)
    assert ok is True

    assert entry.version == 2
    assert entry.minor_version == 1

    assert entry.data[CONF_TRANSPORT] == TRANSPORT_SERIAL
    assert entry.data[CONF_SERIAL_COMPORT] == "/dev/ttyUSB0"
    assert entry.data[CONF_INVERTER_SERIAL_ADDRESS] == 2

    assert "port" not in entry.data
    assert "address" not in entry.data


async def test_migrate_entry_future_version_returns_false(hass: HomeAssistant) -> None:
    """If entry.version > 2, migration should refuse (user downgraded from future)."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Future Aurora",
        data={},
        version=3,
        minor_version=0,
    )
    entry.add_to_hass(hass)

    ok = await async_migrate_entry(hass, entry)
    assert ok is False


async def test_unload_entry_serial(hass: HomeAssistant) -> None:
    """Test unloading the aurora_abb_powerone entry (serial transport)."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Aurora Serial",
        data={
            CONF_TRANSPORT: TRANSPORT_SERIAL,
            CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
            CONF_INVERTER_SERIAL_ADDRESS: 7,
            ATTR_MODEL: "model123",
            ATTR_SERIAL_NUMBER: "876",
            ATTR_FIRMWARE: "1.2.3.4",
        },
        version=CURRENT_VERSION,
    )
    mock_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.aurora_abb_powerone.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.aurora_abb_powerone.async_unload_entry",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_entry_tcp(hass: HomeAssistant) -> None:
    """Test unloading the aurora_abb_powerone entry (TCP transport)."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Aurora TCP",
        data={
            CONF_TRANSPORT: TRANSPORT_TCP,
            CONF_TCP_HOST: "192.168.1.10",
            CONF_TCP_PORT: 8899,
            CONF_INVERTER_SERIAL_ADDRESS: 3,
            ATTR_MODEL: "modelXYZ",
            ATTR_SERIAL_NUMBER: "123",
            ATTR_FIRMWARE: "9.9.9",
        },
        version=CURRENT_VERSION,
    )
    mock_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.aurora_abb_powerone.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.aurora_abb_powerone.async_unload_entry",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_entry.state is ConfigEntryState.NOT_LOADED
