"""Tests for the Bond cover device."""
from datetime import timedelta

from bond_api import Action, DeviceType

from homeassistant import core
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, STATE_CLOSED
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    STATE_UNKNOWN,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import utcnow

from .common import (
    help_test_entity_available,
    patch_bond_action,
    patch_bond_device_state,
    setup_platform,
)

from tests.common import async_fire_time_changed


def shades(name: str):
    """Create motorized shades with given name."""
    return {
        "name": name,
        "type": DeviceType.MOTORIZED_SHADES,
        "actions": ["Open", "Close", "Hold"],
    }


def tilt_only_shades(name: str):
    """Create motorized shades that only tilt."""
    return {
        "name": name,
        "type": DeviceType.MOTORIZED_SHADES,
        "actions": ["TiltOpen", "TiltClose", "Hold"],
    }


def tilt_shades(name: str):
    """Create motorized shades with given name that can also tilt."""
    return {
        "name": name,
        "type": DeviceType.MOTORIZED_SHADES,
        "actions": ["Open", "Close", "Hold", "TiltOpen", "TiltClose", "Hold"],
    }


async def test_entity_registry(hass: core.HomeAssistant):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(
        hass,
        COVER_DOMAIN,
        shades("name-1"),
        bond_version={"bondid": "test-hub-id"},
        bond_device_id="test-device-id",
    )

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["cover.name_1"]
    assert entity.unique_id == "test-hub-id_test-device-id"


async def test_open_cover(hass: core.HomeAssistant):
    """Tests that open cover command delegates to API."""
    await setup_platform(
        hass, COVER_DOMAIN, shades("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_open, patch_bond_device_state():
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_open.assert_called_once_with("test-device-id", Action.open())


async def test_close_cover(hass: core.HomeAssistant):
    """Tests that close cover command delegates to API."""
    await setup_platform(
        hass, COVER_DOMAIN, shades("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_close, patch_bond_device_state():
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_close.assert_called_once_with("test-device-id", Action.close())


async def test_stop_cover(hass: core.HomeAssistant):
    """Tests that stop cover command delegates to API."""
    await setup_platform(
        hass, COVER_DOMAIN, shades("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_hold, patch_bond_device_state():
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_hold.assert_called_once_with("test-device-id", Action.hold())


async def test_tilt_open_cover(hass: core.HomeAssistant):
    """Tests that tilt open cover command delegates to API."""
    await setup_platform(
        hass, COVER_DOMAIN, tilt_only_shades("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_open, patch_bond_device_state():
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_open.assert_called_once_with("test-device-id", Action.tilt_open())
    assert hass.states.get("cover.name_1").state == STATE_UNKNOWN


async def test_tilt_close_cover(hass: core.HomeAssistant):
    """Tests that tilt close cover command delegates to API."""
    await setup_platform(
        hass, COVER_DOMAIN, tilt_only_shades("name-1"), bond_device_id="test-device-id"
    )

    with patch_bond_action() as mock_close, patch_bond_device_state():
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_close.assert_called_once_with("test-device-id", Action.tilt_close())
    assert hass.states.get("cover.name_1").state == STATE_UNKNOWN


async def test_tilt_stop_cover(hass: core.HomeAssistant):
    """Tests that tilt stop cover command delegates to API."""
    await setup_platform(
        hass,
        COVER_DOMAIN,
        tilt_only_shades("name-1"),
        bond_device_id="test-device-id",
        state={"counter1": 123},
    )

    with patch_bond_action() as mock_hold, patch_bond_device_state():
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER_TILT,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_hold.assert_called_once_with("test-device-id", Action.hold())
    assert hass.states.get("cover.name_1").state == STATE_UNKNOWN


async def test_tilt_and_open(hass: core.HomeAssistant):
    """Tests that supports both tilt and open."""
    await setup_platform(
        hass,
        COVER_DOMAIN,
        tilt_shades("name-1"),
        bond_device_id="test-device-id",
        state={"open": False},
    )

    with patch_bond_action() as mock_open, patch_bond_device_state():
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_open.assert_called_once_with("test-device-id", Action.tilt_open())
    assert hass.states.get("cover.name_1").state == STATE_CLOSED


async def test_update_reports_open_cover(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports cover is open."""
    await setup_platform(hass, COVER_DOMAIN, shades("name-1"))

    with patch_bond_device_state(return_value={"open": 1}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("cover.name_1").state == "open"


async def test_update_reports_closed_cover(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports cover is closed."""
    await setup_platform(hass, COVER_DOMAIN, shades("name-1"))

    with patch_bond_device_state(return_value={"open": 0}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("cover.name_1").state == "closed"


async def test_cover_available(hass: core.HomeAssistant):
    """Tests that available state is updated based on API errors."""
    await help_test_entity_available(
        hass, COVER_DOMAIN, shades("name-1"), "cover.name_1"
    )
