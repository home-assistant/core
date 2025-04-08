"""Tests for AVM Fritz!Box switch component."""

from datetime import timedelta
from unittest.mock import Mock, call, patch

from syrupy import SnapshotAssertion

from homeassistant.components.cover import ATTR_POSITION, DOMAIN as COVER_DOMAIN
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICES,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    FritzDeviceCoverMock,
    FritzDeviceCoverUnknownPositionMock,
    set_devices,
    setup_config_entry,
)
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed, snapshot_platform

ENTITY_ID = f"{COVER_DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
) -> None:
    """Test setup of platform."""
    device = FritzDeviceCoverMock()
    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.COVER]):
        entry = await setup_config_entry(
            hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
        )
    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_unknown_position(hass: HomeAssistant, fritz: Mock) -> None:
    """Test cover with unknown position."""
    device = FritzDeviceCoverUnknownPositionMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_open_cover(hass: HomeAssistant, fritz: Mock) -> None:
    """Test opening the cover."""
    device = FritzDeviceCoverMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_blind_open.call_count == 1


async def test_close_cover(hass: HomeAssistant, fritz: Mock) -> None:
    """Test closing the device."""
    device = FritzDeviceCoverMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_blind_close.call_count == 1


async def test_set_position_cover(hass: HomeAssistant, fritz: Mock) -> None:
    """Test stopping the device."""
    device = FritzDeviceCoverMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 50},
        True,
    )
    assert device.set_level_percentage.call_args_list == [call(50, True)]


async def test_stop_cover(hass: HomeAssistant, fritz: Mock) -> None:
    """Test stopping the device."""
    device = FritzDeviceCoverMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_blind_stop.call_count == 1


async def test_discover_new_device(hass: HomeAssistant, fritz: Mock) -> None:
    """Test adding new discovered devices during runtime."""
    device = FritzDeviceCoverMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state

    new_device = FritzDeviceCoverMock()
    new_device.ain = "7890 1234"
    new_device.name = "new_climate"
    set_devices(fritz, devices=[device, new_device])

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{COVER_DOMAIN}.new_climate")
    assert state
