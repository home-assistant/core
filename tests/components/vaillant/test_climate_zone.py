"""Tests for the vaillant zone climate."""

from pymultimatic.model import (
    OperatingModes,
    QuickMode,
    QuickModes,
    QuickVeto,
    SettingModes,
    System,
    Zone,
)
import pytest

from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
import homeassistant.components.vaillant as vaillant
from homeassistant.components.vaillant.const import ATTR_ENDS_AT, ATTR_VAILLANT_MODE

from tests.components.vaillant import (
    SystemManagerMock,
    active_holiday_mode,
    assert_entities_count,
    call_service,
    get_system,
    goto_future,
    setup_vaillant,
    time_program,
)


@pytest.fixture(autouse=True)
def fixture_only_climate(mock_system_manager):
    """Mock vaillant to only handle sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = ["climate"]
    yield
    vaillant.PLATFORMS = orig_platforms


def _assert_zone_state(hass, mode, hvac, current_temp, target_temp=None):
    """Assert zone climate state."""
    state = hass.states.get("climate.vaillant_zone_1")

    assert hass.states.is_state("climate.vaillant_zone_1", hvac)
    assert state.attributes["current_temperature"] == current_temp
    assert state.attributes["max_temp"] == Zone.MAX_TARGET_TEMP
    assert state.attributes["min_temp"] == Zone.MIN_TARGET_TEMP
    assert state.attributes["temperature"] == target_temp
    assert set(state.attributes["hvac_modes"]) == {
        HVAC_MODE_OFF,
        HVAC_MODE_AUTO,
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
    }

    assert state.attributes["supported_features"] == SUPPORT_TARGET_TEMPERATURE

    assert state.attributes[ATTR_VAILLANT_MODE] == mode.name


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await setup_vaillant(hass)
    # one room, one zone
    assert_entities_count(hass, 2)
    zone = SystemManagerMock.system.zones[0]
    _assert_zone_state(
        hass,
        OperatingModes.AUTO,
        HVAC_MODE_AUTO,
        zone.temperature,
        zone.active_mode.target,
    )


async def test_empty_system(hass):
    """Test setup with empty system."""
    assert await setup_vaillant(hass, system=System())
    assert_entities_count(hass, 0)


async def _test_mode_hvac(hass, mode, hvac_mode, target_temp):
    system = get_system()

    if isinstance(mode, QuickMode):
        system.quick_mode = mode
    else:
        system.zones[0].heating.operating_mode = mode

    assert await setup_vaillant(hass, system=system)
    zone = SystemManagerMock.system.zones[0]
    _assert_zone_state(hass, mode, hvac_mode, zone.temperature, target_temp)


async def _test_set_hvac(hass, hvac, mode, current_temp, target_temp):
    assert await setup_vaillant(hass)

    await call_service(
        hass,
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.vaillant_zone_1", "hvac_mode": hvac},
    )

    _assert_zone_state(hass, mode, hvac, current_temp, target_temp)


async def test_day_mode_hvac_heat(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass, OperatingModes.DAY, HVAC_MODE_HEAT, zone.heating.target_high
    )


async def test_night_mode_hvac_cool(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass, OperatingModes.NIGHT, HVAC_MODE_COOL, zone.heating.target_low
    )


async def test_auto_mode_hvac_auto(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass, OperatingModes.AUTO, HVAC_MODE_AUTO, zone.active_mode.target
    )


async def test_off_mode_hvac_off(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    zone.heating.operating_mode = OperatingModes.OFF
    await _test_mode_hvac(hass, OperatingModes.OFF, HVAC_MODE_OFF, Zone.MIN_TARGET_TEMP)


async def test_quickmode_system_off_mode_hvac_off(hass):
    """Test mode <> hvac."""
    await _test_mode_hvac(
        hass, QuickModes.SYSTEM_OFF, HVAC_MODE_OFF, Zone.MIN_TARGET_TEMP
    )


async def test_quickmode_one_day_away_mode_hvac_off(hass):
    """Test mode <> hvac."""
    await _test_mode_hvac(
        hass, QuickModes.ONE_DAY_AWAY, HVAC_MODE_OFF, Zone.MIN_TARGET_TEMP
    )


async def test_quickmode_party_mode_hvac_heat(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass, QuickModes.PARTY, HVAC_MODE_HEAT, zone.heating.target_high
    )


async def test_quickmode_one_day_home_hvac_auto(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_mode_hvac(
        hass, QuickModes.ONE_DAY_AT_HOME, HVAC_MODE_AUTO, zone.heating.target_low
    )


async def test_quickmode_ventilation_boost_hvac_fan(hass):
    """Test mode <> hvac."""
    await _test_mode_hvac(
        hass, QuickModes.VENTILATION_BOOST, HVAC_MODE_FAN_ONLY, Zone.MIN_TARGET_TEMP
    )


async def test_holiday_hvac_off(hass):
    """Test mode <> hvac."""
    system = get_system()
    system.holiday = active_holiday_mode()

    assert await setup_vaillant(hass, system=system)
    _assert_zone_state(
        hass, QuickModes.HOLIDAY, HVAC_MODE_OFF, system.zones[0].temperature, 15
    )


async def test_set_hvac_heat(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_set_hvac(
        hass,
        HVAC_MODE_HEAT,
        OperatingModes.DAY,
        zone.temperature,
        zone.heating.target_high,
    )


async def test_set_hvac_auto(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_set_hvac(
        hass,
        HVAC_MODE_AUTO,
        OperatingModes.AUTO,
        zone.temperature,
        zone.active_mode.target,
    )


async def test_set_hvac_cool(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_set_hvac(
        hass,
        HVAC_MODE_COOL,
        OperatingModes.NIGHT,
        zone.temperature,
        zone.heating.target_low,
    )


async def test_set_hvac_off(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    await _test_set_hvac(
        hass, HVAC_MODE_OFF, OperatingModes.OFF, zone.temperature, Zone.MIN_TARGET_TEMP,
    )


async def test_set_target_temp_cool(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    assert await setup_vaillant(hass)

    await call_service(
        hass,
        "climate",
        "set_temperature",
        {"entity_id": "climate.vaillant_zone_1", "temperature": 14},
    )

    _assert_zone_state(
        hass, OperatingModes.QUICK_VETO, HVAC_MODE_COOL, zone.temperature, 14
    )
    SystemManagerMock.instance.set_zone_quick_veto.assert_called_once()


async def test_set_target_temp_heat(hass):
    """Test mode <> hvac."""
    zone = get_system().zones[0]
    assert await setup_vaillant(hass)

    await call_service(
        hass,
        "climate",
        "set_temperature",
        {"entity_id": "climate.vaillant_zone_1", "temperature": 30},
    )

    _assert_zone_state(
        hass, OperatingModes.QUICK_VETO, HVAC_MODE_HEAT, zone.temperature, 30
    )
    SystemManagerMock.instance.set_zone_quick_veto.assert_called_once()


async def test_state_update_room(hass):
    """Test room climate is updated accordingly to data."""
    assert await setup_vaillant(hass)
    zone = SystemManagerMock.system.zones[0]
    _assert_zone_state(
        hass,
        OperatingModes.AUTO,
        HVAC_MODE_AUTO,
        zone.temperature,
        zone.active_mode.target,
    )

    system = SystemManagerMock.system
    zone = system.zones[0]
    zone.heating.target_high = 30
    zone.heating.time_program = time_program(SettingModes.DAY, None)
    zone.temperature = 25
    await goto_future(hass)

    _assert_zone_state(hass, OperatingModes.AUTO, HVAC_MODE_AUTO, 25, 30)


async def test_state_attrs(hass):
    """Tetst state_attrs are correct."""
    assert await setup_vaillant(hass)
    state = hass.states.get("climate.vaillant_zone_1")
    assert state.attributes[ATTR_ENDS_AT] is not None


async def test_state_attrs_quick_veto(hass):
    """Tetst state_attrs are correct."""
    system = get_system()
    system.zones[0].quick_veto = QuickVeto(duration=None, target=15)
    assert await setup_vaillant(hass, system=system)
    state = hass.states.get("climate.vaillant_zone_1")
    assert state.attributes.get(ATTR_ENDS_AT, None) is None
