"""Tests for the vaillant sensor."""
import datetime
from unittest.mock import ANY

from pymultimatic.model import (
    HolidayMode,
    HotWater,
    OperatingModes,
    QuickModes,
    System,
    constants,
)
import pytest

import homeassistant.components.vaillant as vaillant
from homeassistant.components.vaillant.const import ATTR_ENDS_AT, ATTR_VAILLANT_MODE

from tests.components.vaillant import (
    SystemManagerMock,
    assert_entities_count,
    call_service,
    get_system,
    goto_future,
    setup_vaillant,
)


def _assert_state(hass, mode, temp, current_temp, away_mode):
    assert_entities_count(hass, 1)

    state = hass.states.get("water_heater.vaillant_dhw")
    assert hass.states.is_state("water_heater.vaillant_dhw", mode.name)
    assert state.attributes["min_temp"] == HotWater.MIN_TARGET_TEMP
    assert state.attributes["max_temp"] == HotWater.MAX_TARGET_TEMP
    assert state.attributes["temperature"] == temp
    assert state.attributes["current_temperature"] == current_temp
    assert state.attributes[ATTR_VAILLANT_MODE] == mode.name

    if mode == QuickModes.HOLIDAY:
        assert state.attributes.get("operation_mode") is None
        assert state.attributes.get("away_mode") is None
        assert state.attributes.get("operation_list") is None
    else:
        assert state.attributes["operation_mode"] == mode.name
        assert state.attributes["away_mode"] == away_mode
        assert set(state.attributes["operation_list"]) == {"ON", "OFF", "AUTO"}


@pytest.fixture(autouse=True)
def fixture_only_water_heater(mock_system_manager):
    """Mock vaillant to only handle sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = ["water_heater"]
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await setup_vaillant(hass)
    _assert_state(hass, OperatingModes.AUTO, constants.FROST_PROTECTION_TEMP, 45, "off")


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await setup_vaillant(hass, system=System())
    assert_entities_count(hass, 0)


async def test_state_update(hass):
    """Test water heater is updated accordingly to data."""
    assert await setup_vaillant(hass)
    _assert_state(hass, OperatingModes.AUTO, constants.FROST_PROTECTION_TEMP, 45, "off")

    system = SystemManagerMock.system
    system.dhw.hotwater.temperature = 65
    system.dhw.hotwater.operating_mode = OperatingModes.ON
    system.dhw.hotwater.target_high = 45
    SystemManagerMock.system = system
    await goto_future(hass)

    _assert_state(hass, OperatingModes.ON, 45, 65, "off")


async def test_holiday_mode(hass):
    """Test holiday mode."""
    system = get_system()
    system.quick_mode = QuickModes.HOLIDAY
    system.holiday = HolidayMode(True, datetime.date.today(), datetime.date.today(), 15)

    assert await setup_vaillant(hass, system=system)
    _assert_state(hass, QuickModes.HOLIDAY, constants.FROST_PROTECTION_TEMP, 45, "on")


async def test_away_mode(hass):
    """Test away mode."""
    system = get_system()
    system.dhw.hotwater.operating_mode = OperatingModes.OFF

    assert await setup_vaillant(hass, system=system)
    _assert_state(hass, OperatingModes.OFF, constants.FROST_PROTECTION_TEMP, 45, "on")


async def test_water_boost(hass):
    """Test hot water boost mode."""
    system = get_system()
    system.quick_mode = QuickModes.HOTWATER_BOOST

    assert await setup_vaillant(hass, system=system)
    _assert_state(hass, QuickModes.HOTWATER_BOOST, 40, 45, "off")


async def test_system_off(hass):
    """Test system off mode."""
    system = get_system()
    system.quick_mode = QuickModes.SYSTEM_OFF

    assert await setup_vaillant(hass, system=system)
    _assert_state(
        hass, QuickModes.SYSTEM_OFF, constants.FROST_PROTECTION_TEMP, 45, "on"
    )


async def test_one_day_away(hass):
    """Test one day away mode."""
    system = get_system()
    system.quick_mode = QuickModes.ONE_DAY_AWAY

    assert await setup_vaillant(hass, system=system)
    _assert_state(
        hass, QuickModes.ONE_DAY_AWAY, constants.FROST_PROTECTION_TEMP, 45, "on"
    )


async def test_turn_away_mode_on(hass):
    """Test turn away mode on."""
    assert await setup_vaillant(hass)

    hot_water = SystemManagerMock.system.dhw.hotwater
    hot_water.operating_mode = OperatingModes.OFF
    SystemManagerMock.instance.get_hot_water.return_value = hot_water

    await hass.services.async_call(
        "water_heater",
        "set_away_mode",
        {"entity_id": "water_heater.vaillant_dhw", "away_mode": True},
    )
    await hass.async_block_till_done()

    SystemManagerMock.instance.set_hot_water_operating_mode.assert_called_once_with(
        ANY, OperatingModes.OFF
    )
    _assert_state(hass, OperatingModes.OFF, constants.FROST_PROTECTION_TEMP, 45, "on")


async def test_turn_away_mode_off(hass):
    """Test turn away mode off."""
    assert await setup_vaillant(hass)

    hot_water = SystemManagerMock.system.dhw.hotwater
    hot_water.operating_mode = OperatingModes.AUTO
    SystemManagerMock.instance.get_hot_water.return_value = hot_water

    await hass.services.async_call(
        "water_heater",
        "set_away_mode",
        {"entity_id": "water_heater.vaillant_dhw", "away_mode": False},
    )
    await hass.async_block_till_done()

    SystemManagerMock.instance.set_hot_water_operating_mode.assert_called_once_with(
        ANY, OperatingModes.AUTO
    )

    _assert_state(hass, OperatingModes.AUTO, constants.FROST_PROTECTION_TEMP, 45, "off")


async def test_set_operating_mode(hass):
    """Test set operation mode."""
    assert await setup_vaillant(hass)

    hot_water = SystemManagerMock.system.dhw.hotwater
    hot_water.operating_mode = OperatingModes.ON
    SystemManagerMock.instance.get_hot_water.return_value = hot_water

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {"entity_id": "water_heater.vaillant_dhw", "operation_mode": "ON"},
    )
    await hass.async_block_till_done()

    SystemManagerMock.instance.set_hot_water_operating_mode.assert_called_once_with(
        ANY, OperatingModes.ON
    )
    _assert_state(hass, OperatingModes.ON, 40, 45, "off")


async def test_set_operating_mode_wrong(hass):
    """Test set operation mode with wrong mode."""
    assert await setup_vaillant(hass)

    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {"entity_id": "water_heater.vaillant_dhw", "operation_mode": "wrong"},
    )
    await hass.async_block_till_done()

    SystemManagerMock.instance.set_hot_water_operating_mode.assert_not_called()
    _assert_state(hass, OperatingModes.AUTO, constants.FROST_PROTECTION_TEMP, 45, "off")


async def test_set_temperature(hass):
    """Test set target temperature."""
    system = get_system()
    system.dhw.hotwater.operating_mode = OperatingModes.AUTO
    assert await setup_vaillant(hass, system=system)

    SystemManagerMock.instance.get_hot_water.return_value = (
        SystemManagerMock.system.dhw.hotwater
    )

    await call_service(
        hass,
        "water_heater",
        "set_temperature",
        {"entity_id": "water_heater.vaillant_dhw", "temperature": 50},
    )

    SystemManagerMock.instance.set_hot_water_setpoint_temperature.assert_called_once_with(
        "dhw", 50
    )
    SystemManagerMock.instance.set_hot_water_operating_mode.assert_not_called()


async def test_set_temperature_already_on(hass):
    """Test set target temperature."""
    system = get_system()
    system.dhw.hotwater.operating_mode = OperatingModes.ON
    assert await setup_vaillant(hass, system=system)

    SystemManagerMock.instance.get_hot_water.return_value = (
        SystemManagerMock.system.dhw.hotwater
    )

    await call_service(
        hass,
        "water_heater",
        "set_temperature",
        {"entity_id": "water_heater.vaillant_dhw", "temperature": 50},
    )

    SystemManagerMock.instance.set_hot_water_setpoint_temperature.assert_called_once_with(
        "dhw", 50
    )
    SystemManagerMock.instance.set_hot_water_operating_mode.assert_not_called()


async def test_set_temperature_already_off(hass):
    """Test set target temperature."""
    system = get_system()
    system.dhw.hotwater.operating_mode = OperatingModes.OFF
    assert await setup_vaillant(hass, system=system)

    SystemManagerMock.instance.get_hot_water.return_value = (
        SystemManagerMock.system.dhw.hotwater
    )

    await call_service(
        hass,
        "water_heater",
        "set_temperature",
        {"entity_id": "water_heater.vaillant_dhw", "temperature": 50},
    )

    SystemManagerMock.instance.set_hot_water_setpoint_temperature.assert_called_once_with(
        "dhw", 50
    )
    SystemManagerMock.instance.set_hot_water_operating_mode.assert_called_once()


async def test_set_operating_mode_while_quick_mode(hass):
    """Ensure water heater mode is set when unrelated quick mode is active."""
    system = get_system()
    system.quick_mode = QuickModes.PARTY
    assert await setup_vaillant(hass, system=system)

    await call_service(
        hass,
        "water_heater",
        "set_operation_mode",
        {"entity_id": "water_heater.vaillant_dhw", "operation_mode": "AUTO"},
    )
    SystemManagerMock.instance.set_hot_water_operating_mode.assert_called_once_with(
        "dhw", OperatingModes.AUTO
    )
    SystemManagerMock.instance.remove_quick_mode.assert_not_called()


async def test_set_operating_mode_while_quick_mode_for_dhw(hass):
    """Ensure water heater mode is not set when related quick mode is active."""
    system = get_system()
    system.quick_mode = QuickModes.HOTWATER_BOOST
    assert await setup_vaillant(hass, system=system)

    await call_service(
        hass,
        "water_heater",
        "set_operation_mode",
        {"entity_id": "water_heater.vaillant_dhw", "operation_mode": "AUTO"},
    )
    SystemManagerMock.instance.set_hot_water_operating_mode.assert_called_once_with(
        "dhw", OperatingModes.AUTO
    )
    SystemManagerMock.instance.remove_quick_mode.assert_called_once_with()


async def test_state_attrs(hass):
    """Tetst state_attrs are correct."""
    assert await setup_vaillant(hass)
    state = hass.states.get("water_heater.vaillant_dhw")
    assert state.attributes[ATTR_ENDS_AT] is not None
