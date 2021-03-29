"""Tests for iaqualink integration."""

import asyncio
from unittest.mock import AsyncMock, patch

from iaqualink.device import (
    AqualinkAuxToggle,
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkLightToggle,
    AqualinkSensor,
    AqualinkThermostat,
)
import iaqualink.exception
from iaqualink.system import AqualinkSystem
import pytest

from homeassistant.components import iaqualink as ha_iaqualink
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from . import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry, mock_coro

async_noop = AsyncMock(return_value=None)


def _(cls, data=None):
    """Create an aqualink class instance with little syntactic overhead."""
    return cls(None, data if data else {})


MOCK_CONFIG = MockConfigEntry(domain=ha_iaqualink.DOMAIN, data=MOCK_CONFIG_DATA)
MOCK_SYSTEMS = {"SERIAL": _(AqualinkSystem)}
MOCK_UNKNOWN_DEVICES = {"1": _(AqualinkDevice)}
MOCK_DEVICES = {
    "1": _(AqualinkAuxToggle),
    "2": _(AqualinkBinarySensor),
    "3": _(AqualinkLightToggle),
    "4": _(AqualinkSensor),
    "5": _(AqualinkThermostat),
}


async def test_no_config_creates_no_entry(hass):
    """Test for when there is no iaqualink in config."""
    with patch(
        "homeassistant.components.iaqualink.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup:
        await async_setup_component(hass, ha_iaqualink.DOMAIN, {})
        await hass.async_block_till_done()

    mock_setup.assert_not_called()


async def test_setup_login_exception(hass):
    """..."""
    entry = MOCK_CONFIG
    entry.add_to_hass(hass)

    with patch(
        "iaqualink.client.AqualinkClient.login",
        side_effect=iaqualink.exception.AqualinkServiceException,
    ):
        assert not await ha_iaqualink.async_setup_entry(hass, entry)


async def test_setup_login_timeout(hass):
    """..."""
    entry = MOCK_CONFIG
    entry.add_to_hass(hass)

    with patch(
        "iaqualink.client.AqualinkClient.login",
        side_effect=asyncio.TimeoutError,
    ), pytest.raises(ConfigEntryNotReady):
        await ha_iaqualink.async_setup_entry(hass, entry)


async def test_setup_systems_exception(hass):
    """..."""
    entry = MOCK_CONFIG
    entry.add_to_hass(hass)

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems",
        side_effect=iaqualink.exception.AqualinkServiceException,
    ), pytest.raises(ConfigEntryNotReady):
        await ha_iaqualink.async_setup_entry(hass, entry)


async def test_setup_devices_exception(hass):
    """..."""
    entry = MOCK_CONFIG
    entry.add_to_hass(hass)

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems", return_value=MOCK_SYSTEMS
    ), patch(
        "iaqualink.system.AqualinkSystem.get_devices",
        side_effect=iaqualink.exception.AqualinkServiceException,
    ), pytest.raises(
        ConfigEntryNotReady
    ):
        await ha_iaqualink.async_setup_entry(hass, entry)


async def test_setup_all_good_no_recognized_devices(hass):
    """..."""
    entry = MOCK_CONFIG
    entry.add_to_hass(hass)

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems", return_value=MOCK_SYSTEMS
    ), patch(
        "iaqualink.system.AqualinkSystem.get_devices", return_value=MOCK_UNKNOWN_DEVICES
    ):
        assert await ha_iaqualink.async_setup_entry(hass, entry)

    assert hass.data[ha_iaqualink.DOMAIN][BINARY_SENSOR_DOMAIN] == []
    assert hass.data[ha_iaqualink.DOMAIN][CLIMATE_DOMAIN] == []
    assert hass.data[ha_iaqualink.DOMAIN][LIGHT_DOMAIN] == []
    assert hass.data[ha_iaqualink.DOMAIN][SENSOR_DOMAIN] == []
    assert hass.data[ha_iaqualink.DOMAIN][SWITCH_DOMAIN] == []


async def test_setup_all_good_all_device_types(hass):
    """..."""
    entry = MOCK_CONFIG
    entry.add_to_hass(hass)

    with patch("iaqualink.client.AqualinkClient.login", return_value=None), patch(
        "iaqualink.client.AqualinkClient.get_systems", return_value=MOCK_SYSTEMS
    ), patch("iaqualink.system.AqualinkSystem.get_devices", return_value=MOCK_DEVICES):
        assert await ha_iaqualink.async_setup_entry(hass, entry)

    assert len(hass.data[ha_iaqualink.DOMAIN][BINARY_SENSOR_DOMAIN]) == 1
    assert len(hass.data[ha_iaqualink.DOMAIN][CLIMATE_DOMAIN]) == 1
    assert len(hass.data[ha_iaqualink.DOMAIN][LIGHT_DOMAIN]) == 1
    assert len(hass.data[ha_iaqualink.DOMAIN][SENSOR_DOMAIN]) == 1
    assert len(hass.data[ha_iaqualink.DOMAIN][SWITCH_DOMAIN]) == 1
