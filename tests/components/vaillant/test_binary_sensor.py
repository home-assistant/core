"""Tests for the vaillant sensor."""
from pymultimatic.model import (
    Device,
    HolidayMode,
    OperatingModes,
    Room,
    SettingModes,
    System,
)
import pytest

import homeassistant.components.vaillant as vaillant

from tests.components.vaillant import (
    SystemManagerMock,
    active_holiday_mode,
    assert_entities_count,
    goto_future,
    setup_vaillant,
    time_program,
)


@pytest.fixture(autouse=True)
def fixture_only_binary_sensor(mock_system_manager):
    """Mock vaillant to only handle binary_sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = ["binary_sensor"]
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await setup_vaillant(hass)
    assert_entities_count(hass, 10)


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await setup_vaillant(hass, system=System())
    assert_entities_count(hass, 2)


async def test_state_update(hass):
    """Test all sensors are updated accordingly to data."""
    assert await setup_vaillant(hass)
    assert_entities_count(hass, 10)

    assert hass.states.is_state("binary_sensor.vaillant_dhw", "off")
    assert hass.states.is_state("binary_sensor.vaillant_room_1_window", "off")
    assert hass.states.is_state("binary_sensor.vaillant_123456789_lock", "on")
    assert hass.states.is_state("binary_sensor.vaillant_123456789_battery", "off")
    assert hass.states.is_state("binary_sensor.vaillant_boiler", "off")
    assert hass.states.is_state("binary_sensor.vaillant_123456789_connectivity", "on")
    assert hass.states.is_state("binary_sensor.vaillant_system_update", "off")
    assert hass.states.is_state("binary_sensor.vaillant_system_online", "on")
    assert hass.states.is_state("binary_sensor.vaillant_holiday", "off")
    state = hass.states.get("binary_sensor.vaillant_holiday")
    assert state.attributes.get("start_date") is None
    assert state.attributes.get("end_date") is None
    assert state.attributes.get("temperature") is None
    assert hass.states.is_state("binary_sensor.vaillant_quick_mode", "off")

    system = SystemManagerMock.system
    system.dhw.circulation.time_program = time_program(SettingModes.ON, None)
    system.dhw.circulation.operating_mode = OperatingModes.AUTO

    room_device = Device("Device 1", "123456789", "VALVE", True, True)
    system.set_room(
        "1",
        Room(
            id="1",
            name="Room 1",
            time_program=time_program(None, 20),
            temperature=22,
            target_high=24,
            operating_mode=OperatingModes.AUTO,
            quick_veto=None,
            child_lock=True,
            window_open=True,
            devices=[room_device],
        ),
    )

    system.boiler_status.status_code = "F11"
    system.info.online = "OFFLINE"
    system.info.update = "UPDATE_PENDING"
    system.holiday = active_holiday_mode()
    SystemManagerMock.system = system

    await goto_future(hass)

    assert_entities_count(hass, 10)
    assert hass.states.is_state("binary_sensor.vaillant_dhw", "off")
    assert hass.states.is_state("binary_sensor.vaillant_room_1_window", "on")
    assert hass.states.is_state("binary_sensor.vaillant_123456789_lock", "off")
    assert hass.states.is_state("binary_sensor.vaillant_123456789_battery", "on")
    assert hass.states.is_state("binary_sensor.vaillant_boiler", "on")
    assert hass.states.is_state("binary_sensor.vaillant_123456789_connectivity", "off")
    assert hass.states.is_state("binary_sensor.vaillant_system_update", "on")
    assert hass.states.is_state("binary_sensor.vaillant_system_online", "off")
    assert hass.states.is_state("binary_sensor.vaillant_holiday", "on")
    state = hass.states.get("binary_sensor.vaillant_holiday")
    assert state.attributes["start_date"] == system.holiday.start_date.isoformat()
    assert state.attributes["end_date"] == system.holiday.end_date.isoformat()
    assert state.attributes["temperature"] == system.holiday.target
    assert hass.states.is_state("binary_sensor.vaillant_quick_mode", "off")

    system.holiday = HolidayMode(False)

    await goto_future(hass)
    assert hass.states.is_state("binary_sensor.vaillant_dhw", "on")
