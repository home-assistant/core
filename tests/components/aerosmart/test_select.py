"""Tests for the aerosmart select platform."""

from aerosmart_modbus.enums import VentilationMode
from modbus_connection.mock import MockModbusUnit
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aerosmart.select import (
    OPTION_TO_VENTILATION_MODE,
    SELECT_DESCRIPTION,
    VENTILATION_MODE_TO_OPTION,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

VENTILATION_MODE = "select.aerosmart_ventilation_mode"


async def test_ventilation_mode_select(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_unit_ventilation: MockModbusUnit,
) -> None:
    """Test ventilation mode state and confirmed write."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(VENTILATION_MODE)
    assert state is not None
    assert state.state == "automatic"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: VENTILATION_MODE, ATTR_OPTION: "manual_1"},
        blocking=True,
    )

    assert [
        mock_modbus_unit_ventilation.holding[address] for address in (5002, 5003)
    ] == [0, 1]
    state = hass.states.get(VENTILATION_MODE)
    assert state is not None
    assert state.state == "manual_1"


async def test_select_options_match_library_metadata(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test select options cover the documented library enum."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    metadata = mock_config_entry.runtime_data.device.ventilation.require_metadata_for(
        "betriebsart"
    )
    assert metadata.value_kind == "enum"
    assert metadata.verified_writable is True
    assert metadata.enum is not None
    assert metadata.enum.enum_type is VentilationMode
    documented_modes = [VentilationMode(value) for value, _ in metadata.enum.options]
    assert list(VENTILATION_MODE_TO_OPTION) == documented_modes
    assert SELECT_DESCRIPTION.options == [
        VENTILATION_MODE_TO_OPTION[mode] for mode in documented_modes
    ]
    assert {
        option: mode for mode, option in VENTILATION_MODE_TO_OPTION.items()
    } == OPTION_TO_VENTILATION_MODE
