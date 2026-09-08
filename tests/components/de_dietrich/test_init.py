"""Test the De Dietrich setup."""

from unittest.mock import patch

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection

from homeassistant.components.de_dietrich.const import (
    CONF_SYSTEM,
    DEFAULT_UNIT_ID,
    DOMAIN,
    SYSTEM_DIEMATIC_3,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_ENTRY_ID, MOCK_TITLE, MOCK_USER_INPUT, seed_boiler

from tests.common import MockConfigEntry


async def test_setup_retry_when_identity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test setup is retried when the boiler identity cannot be read."""
    mock_connection.for_unit(DEFAULT_UNIT_ID).fail_read(457, ModbusTimeoutError("boom"))
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_base_layout_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test base-layout device information omits unavailable metadata."""
    seed_boiler(mock_connection.for_unit(DEFAULT_UNIT_ID))
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        data={**MOCK_USER_INPUT, CONF_SYSTEM: SYSTEM_DIEMATIC_3},
        title=MOCK_TITLE,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None
    assert device.name == "De Dietrich"
    assert device.manufacturer == "De Dietrich"
    assert device.model is None
    assert device.serial_number is None
    assert device.sw_version is None
