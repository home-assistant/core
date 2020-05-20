"""Tests for service."""
from pymultimatic.model import QuickModes, QuickVeto
import pytest
import voluptuous

from homeassistant.components import vaillant
from homeassistant.components.vaillant import DOMAIN

from tests.components.vaillant import (
    SystemManagerMock,
    active_holiday_mode,
    call_service,
    get_system,
    setup_vaillant,
)


@pytest.fixture(autouse=True)
def fixture_only_climate(mock_system_manager):
    """Mock vaillant to only handle binary_sensor."""
    orig_platforms = vaillant.PLATFORMS
    vaillant.PLATFORMS = ["climate"]
    yield
    vaillant.PLATFORMS = orig_platforms


async def test_valid_config(hass):
    """Test setup with valid config."""
    assert await setup_vaillant(hass)
    assert len(hass.services.async_services()[DOMAIN]) == 7


async def test_remove_quick_mode(hass):
    """Test remove existing quick mode."""
    system = get_system()
    system.quick_mode = QuickModes.ONE_DAY_AT_HOME
    assert await setup_vaillant(hass, system=system)
    await call_service(hass, "vaillant", "remove_quick_mode", None)
    SystemManagerMock.instance.remove_quick_mode.assert_called_once_with()


async def test_remove_quick_mode_wrong_data(hass):
    """Test remove existing quick mode with wrong data."""
    assert await setup_vaillant(hass)
    with pytest.raises(voluptuous.error.MultipleInvalid):
        await call_service(hass, "vaillant", "remove_quick_mode", {"test": "boom"})


async def test_remove_holiday_mode(hass):
    """Remove existing holiday mode."""
    system = get_system()
    system.holiday = active_holiday_mode()
    assert await setup_vaillant(hass, system=system)
    await call_service(hass, "vaillant", "remove_holiday_mode", None)
    SystemManagerMock.instance.remove_holiday_mode.assert_called_once_with()


async def test_remove_holiday_mode_wrong_data(hass):
    """Remove existing holiday mode with wrong data."""
    assert await setup_vaillant(hass)
    with pytest.raises(voluptuous.error.MultipleInvalid):
        await call_service(hass, "vaillant", "remove_holiday_mode", {"test": "boom"})


async def test_set_quick_mode(hass):
    """Set quick mode."""
    assert await setup_vaillant(hass)
    await call_service(hass, "vaillant", "set_quick_mode", {"quick_mode": "QM_PARTY"})
    SystemManagerMock.instance.set_quick_mode.assert_called_once_with(QuickModes.PARTY)


async def test_set_quick_mode_wrong_data(hass):
    """Set quick mode with wrong data."""
    assert await setup_vaillant(hass)
    with pytest.raises(voluptuous.error.MultipleInvalid):
        await call_service(hass, "vaillant", "set_quick_mode", {"test": "boom"})


async def test_set_holiday_mode_correct_date(hass):
    """Test holiday mode."""
    assert await setup_vaillant(hass)
    await call_service(
        hass,
        "vaillant",
        "set_holiday_mode",
        {"start_date": "2010-10-25", "end_date": "2010-10-26", "temperature": "10"},
    )
    SystemManagerMock.instance.set_holiday_mode.assert_called_once()


async def test_set_holiday_mode_wrong_date_format(hass):
    """Test holiday mode."""
    assert await setup_vaillant(hass)
    await call_service(
        hass,
        "vaillant",
        "set_holiday_mode",
        {
            "start_date": "2010-10-25T00:00:00.000Z",
            "end_date": "2010-10-26T00:00:00.000Z",
            "temperature": "10",
        },
    )
    SystemManagerMock.instance.set_holiday_mode.assert_called_once()


async def test_set_holiday_mode_wrong_data(hass):
    """Test holiday mode with wrong data."""
    assert await setup_vaillant(hass)
    with pytest.raises(voluptuous.error.MultipleInvalid):
        await call_service(hass, "vaillant", "set_holiday_mode", {"test": "boom"})


async def test_remove_quick_veto_wrong_data(hass):
    """Remove quick veto with wrong entity id."""
    assert await setup_vaillant(hass)
    await call_service(
        hass, "vaillant", "remove_quick_veto", {"entity_id": "climate.vaillant_test123"}
    )
    SystemManagerMock.instance.remove_room_quick_veto.assert_not_called()
    SystemManagerMock.instance.remove_zone_quick_veto.assert_not_called()


async def test_remove_quick_veto_room(hass):
    """Remove quick veto with already existing quick veto."""
    system = get_system()
    system.rooms[0].quick_veto = QuickVeto(duration=30, target=10)
    assert await setup_vaillant(hass, system=system)
    await call_service(
        hass, "vaillant", "remove_quick_veto", {"entity_id": "climate.vaillant_room_1"}
    )
    SystemManagerMock.instance.remove_room_quick_veto.assert_called_once_with("1")


async def test_no_remove_quick_veto_room(hass):
    """Remove quick veto without quick veto."""
    assert await setup_vaillant(hass)
    await call_service(
        hass, "vaillant", "remove_quick_veto", {"entity_id": "climate.vaillant_room_1"}
    )
    SystemManagerMock.instance.remove_room_quick_veto.assert_not_called()


async def test_no_remove_quick_veto_zone(hass):
    """Remove quick veto without quick veto."""
    assert await setup_vaillant(hass)
    await call_service(
        hass, "vaillant", "remove_quick_veto", {"entity_id": "climate.vaillant_zone_1"}
    )
    SystemManagerMock.instance.remove_zone_quick_veto.assert_not_called()


async def test_remove_quick_veto_zone(hass):
    """Remove quick veto with already existing quick veto."""
    system = get_system()
    system.zones[0].quick_veto = QuickVeto(duration=30, target=10)
    assert await setup_vaillant(hass, system=system)
    await call_service(
        hass, "vaillant", "remove_quick_veto", {"entity_id": "climate.vaillant_zone_1"}
    )
    SystemManagerMock.instance.remove_zone_quick_veto.assert_called_once_with("zone_1")


async def test_set_quick_veto_room(hass):
    """Set quick veto without quick veto."""
    assert await setup_vaillant(hass)
    await call_service(
        hass,
        DOMAIN,
        "set_quick_veto",
        {"entity_id": "climate.vaillant_room_1", "duration": 300, "temperature": 25},
    )
    SystemManagerMock.instance.set_room_quick_veto.assert_called_once_with(
        "1", QuickVeto(300, 25.0)
    )


async def test_set_quick_veto_room_with_quick_veto(hass):
    """Set quick veto with quick veto."""
    system = get_system()
    system.rooms[0].quick_veto = QuickVeto(duration=30, target=10)
    assert await setup_vaillant(hass, system=system)
    await call_service(
        hass,
        DOMAIN,
        "set_quick_veto",
        {"entity_id": "climate.vaillant_room_1", "duration": 300, "temperature": 25},
    )
    SystemManagerMock.instance.set_room_quick_veto.assert_called_once_with(
        "1", QuickVeto(300, 25.0)
    )
    SystemManagerMock.instance.remove_room_quick_veto.assert_called_once_with("1")


async def test_set_quick_veto_zone_with_quick_veto(hass):
    """Set quick veto with quick veto."""
    system = get_system()
    system.zones[0].quick_veto = QuickVeto(duration=30, target=10)
    assert await setup_vaillant(hass, system=system)
    await call_service(
        hass,
        DOMAIN,
        "set_quick_veto",
        {"entity_id": "climate.vaillant_zone_1", "duration": 300, "temperature": 25},
    )
    SystemManagerMock.instance.set_zone_quick_veto.assert_called_once_with(
        "zone_1", QuickVeto(300, 25.0)
    )
    SystemManagerMock.instance.remove_zone_quick_veto.assert_called_once_with("zone_1")


async def test_set_quick_veto_zone(hass):
    """Set quick veto without quick veto."""
    assert await setup_vaillant(hass)
    await call_service(
        hass,
        DOMAIN,
        "set_quick_veto",
        {"entity_id": "climate.vaillant_zone_1", "duration": 300, "temperature": 25},
    )
    SystemManagerMock.instance.set_zone_quick_veto.assert_called_once_with(
        "zone_1", QuickVeto(300, 25.0)
    )
