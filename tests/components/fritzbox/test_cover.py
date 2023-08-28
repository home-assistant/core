"""Tests for AVM Fritz!Box switch component."""
from unittest.mock import Mock, call

from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_POSITION, DOMAIN
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICES,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant

from . import FritzDeviceCoverMock, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

ENTITY_ID = f"{DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(hass: HomeAssistant, fritz: Mock) -> None:
    """Test setup of platform."""
    device = FritzDeviceCoverMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_open_cover(hass: HomeAssistant, fritz: Mock) -> None:
    """Test opening the cover."""
    device = FritzDeviceCoverMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_blind_open.call_count == 1


async def test_close_cover(hass: HomeAssistant, fritz: Mock) -> None:
    """Test closing the device."""
    device = FritzDeviceCoverMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_blind_close.call_count == 1


async def test_set_position_cover(hass: HomeAssistant, fritz: Mock) -> None:
    """Test stopping the device."""
    device = FritzDeviceCoverMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 50},
        True,
    )
    assert device.set_level_percentage.call_args_list == [call(50)]


async def test_stop_cover(hass: HomeAssistant, fritz: Mock) -> None:
    """Test stopping the device."""
    device = FritzDeviceCoverMock()
    assert await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: ENTITY_ID}, True
    )
    assert device.set_blind_stop.call_count == 1
