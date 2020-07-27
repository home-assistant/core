"""Test deCONZ component setup process."""
import asyncio
from copy import deepcopy

from homeassistant.components import deconz

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.async_mock import patch

ENTRY1_HOST = "1.2.3.4"
ENTRY1_PORT = 80
ENTRY1_API_KEY = "1234567890ABCDEF"
ENTRY1_BRIDGEID = "12345ABC"
ENTRY1_UUID = "456DEF"

ENTRY2_HOST = "2.3.4.5"
ENTRY2_PORT = 80
ENTRY2_API_KEY = "1234567890ABCDEF"
ENTRY2_BRIDGEID = "23456DEF"
ENTRY2_UUID = "789ACE"


async def setup_entry(hass, entry):
    """Test that setup entry works."""
    with patch.object(
        deconz.DeconzGateway, "async_setup", return_value=True
    ), patch.object(
        deconz.DeconzGateway, "async_update_device_registry", return_value=True
    ):
        assert await deconz.async_setup_entry(hass, entry) is True


async def test_setup_entry_fails(hass):
    """Test setup entry fails if deCONZ is not available."""
    with patch("pydeconz.DeconzSession.initialize", side_effect=Exception):
        await setup_deconz_integration(hass)
    assert not hass.data[deconz.DOMAIN]


async def test_setup_entry_no_available_bridge(hass):
    """Test setup entry fails if deCONZ is not available."""
    with patch("pydeconz.DeconzSession.initialize", side_effect=asyncio.TimeoutError):
        await setup_deconz_integration(hass)
    assert not hass.data[deconz.DOMAIN]


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    gateway = await setup_deconz_integration(hass)

    assert hass.data[deconz.DOMAIN]
    assert gateway.bridgeid in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN][gateway.bridgeid].master


async def test_setup_entry_multiple_gateways(hass):
    """Test setup entry is successful with multiple gateways."""
    gateway = await setup_deconz_integration(hass)

    data = deepcopy(DECONZ_WEB_REQUEST)
    data["config"]["bridgeid"] = "01234E56789B"
    gateway2 = await setup_deconz_integration(
        hass, get_state_response=data, entry_id="2"
    )

    assert len(hass.data[deconz.DOMAIN]) == 2
    assert hass.data[deconz.DOMAIN][gateway.bridgeid].master
    assert not hass.data[deconz.DOMAIN][gateway2.bridgeid].master


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    gateway = await setup_deconz_integration(hass)
    assert hass.data[deconz.DOMAIN]

    assert await deconz.async_unload_entry(hass, gateway.config_entry)
    assert not hass.data[deconz.DOMAIN]


async def test_unload_entry_multiple_gateways(hass):
    """Test being able to unload an entry and master gateway gets moved."""
    gateway = await setup_deconz_integration(hass)

    data = deepcopy(DECONZ_WEB_REQUEST)
    data["config"]["bridgeid"] = "01234E56789B"
    gateway2 = await setup_deconz_integration(
        hass, get_state_response=data, entry_id="2"
    )

    assert len(hass.data[deconz.DOMAIN]) == 2

    assert await deconz.async_unload_entry(hass, gateway.config_entry)

    assert len(hass.data[deconz.DOMAIN]) == 1
    assert hass.data[deconz.DOMAIN][gateway2.bridgeid].master
