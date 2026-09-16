"""Test the De Dietrich water heater platform."""

from unittest.mock import patch

from diematic_modbus import HotWaterMode
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.de_dietrich.const import DEFAULT_UNIT_ID, DOMAIN
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ECO,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import seed_boiler, seed_isystem_boiler

from tests.common import MockConfigEntry


async def test_water_heater_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the water heater entity exposes the expected state on a present bundle."""
    state = hass.states.get("water_heater.de_dietrich_hot_water")
    assert state is not None
    assert state.state == STATE_ECO
    assert state.attributes["current_temperature"] == 45.0
    assert state.attributes["operation_list"] == [
        STATE_ECO,
        STATE_PERFORMANCE,
        STATE_HIGH_DEMAND,
    ]
    assert state.attributes["min_temp"] == 1.0
    assert state.attributes["max_temp"] == 80.0
    assert state.attributes["target_temp_step"] == 1.0
    assert (
        state.attributes["supported_features"] == 3
    )  # TARGET_TEMPERATURE | OPERATION_MODE


async def test_water_heater_set_operation_mode_writes_boiler(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test set_operation_mode maps the HA mode and writes via the lib."""
    unit = mock_connection.for_unit(DEFAULT_UNIT_ID)
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {ATTR_OPERATION_MODE: STATE_HIGH_DEMAND},
        target={ATTR_ENTITY_ID: "water_heater.de_dietrich_hot_water"},
        blocking=True,
    )
    # iSystem uses register 659 (mask 0x50) for the hot-water mode.
    assert unit.holding[659] == HotWaterMode.PERM


async def test_water_heater_set_temperature_writes_day_target(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test set_temperature writes to the day-target register on the iSystem layout."""
    unit = mock_connection.for_unit(DEFAULT_UNIT_ID)
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_TEMPERATURE: 55.0},
        target={ATTR_ENTITY_ID: "water_heater.de_dietrich_hot_water"},
        blocking=True,
    )
    # iSystem day_target register 672, float10 scaled by 10.
    assert unit.holding[672] == 550


async def test_water_heater_set_temperature_translates_modbus_error(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test set_temperature raises HomeAssistantError when the boiler fails."""
    # iSystem day_target register 672.
    mock_connection.for_unit(DEFAULT_UNIT_ID).fail_write(
        672, ModbusTimeoutError("boom")
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 55.0},
            target={ATTR_ENTITY_ID: "water_heater.de_dietrich_hot_water"},
            blocking=True,
        )


async def test_water_heater_current_temperature_falls_back_to_dpsm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test base-layout current_temperature uses temp_dpsm when temp is invalid."""
    unit = mock_connection.for_unit(DEFAULT_UNIT_ID)
    seed_boiler(unit)
    # Invalidate the main temp register, then set a valid DPSM reading.
    unit.holding[62] = 0xFFFF
    unit.holding[459] = 555
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("water_heater.de_dietrich_hot_water")
    assert state is not None
    assert state.attributes["current_temperature"] == 55.5


async def test_water_heater_skipped_when_hot_water_absent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no water heater entity is created when the bundle has no live readings."""
    unit = mock_connection.for_unit(DEFAULT_UNIT_ID)
    seed_isystem_boiler(unit)
    for register in (603,):  # hot_water.temp
        unit.holding[register] = 0xFFFF
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.de_dietrich.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        WATER_HEATER_DOMAIN, DOMAIN, f"{mock_config_entry.entry_id}_hot_water"
    )
    assert entity_id is None
