"""Test deCONZ component setup process."""

import asyncio
from copy import deepcopy
from unittest.mock import patch

from homeassistant.components.deconz import (
    DeconzGateway,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

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
    with patch.object(DeconzGateway, "async_setup", return_value=True), patch.object(
        DeconzGateway, "async_update_device_registry", return_value=True
    ):
        assert await async_setup_entry(hass, entry) is True


async def test_setup_entry_fails(hass):
    """Test setup entry fails if deCONZ is not available."""
    with patch("pydeconz.DeconzSession.initialize", side_effect=Exception):
        await setup_deconz_integration(hass)
    assert not hass.data[DECONZ_DOMAIN]


async def test_setup_entry_no_available_bridge(hass):
    """Test setup entry fails if deCONZ is not available."""
    with patch("pydeconz.DeconzSession.initialize", side_effect=asyncio.TimeoutError):
        await setup_deconz_integration(hass)
    assert not hass.data[DECONZ_DOMAIN]


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    config_entry = await setup_deconz_integration(hass)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert hass.data[DECONZ_DOMAIN]
    assert gateway.bridgeid in hass.data[DECONZ_DOMAIN]
    assert hass.data[DECONZ_DOMAIN][gateway.bridgeid].master


async def test_setup_entry_multiple_gateways(hass):
    """Test setup entry is successful with multiple gateways."""
    config_entry = await setup_deconz_integration(hass)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    data = deepcopy(DECONZ_WEB_REQUEST)
    data["config"]["bridgeid"] = "01234E56789B"
    config_entry2 = await setup_deconz_integration(
        hass, get_state_response=data, entry_id="2"
    )
    gateway2 = get_gateway_from_config_entry(hass, config_entry2)

    assert len(hass.data[DECONZ_DOMAIN]) == 2
    assert hass.data[DECONZ_DOMAIN][gateway.bridgeid].master
    assert not hass.data[DECONZ_DOMAIN][gateway2.bridgeid].master


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    config_entry = await setup_deconz_integration(hass)
    assert hass.data[DECONZ_DOMAIN]

    assert await async_unload_entry(hass, config_entry)
    assert not hass.data[DECONZ_DOMAIN]


async def test_unload_entry_multiple_gateways(hass):
    """Test being able to unload an entry and master gateway gets moved."""
    config_entry = await setup_deconz_integration(hass)

    data = deepcopy(DECONZ_WEB_REQUEST)
    data["config"]["bridgeid"] = "01234E56789B"
    config_entry2 = await setup_deconz_integration(
        hass, get_state_response=data, entry_id="2"
    )
    gateway2 = get_gateway_from_config_entry(hass, config_entry2)

    assert len(hass.data[DECONZ_DOMAIN]) == 2

    assert await async_unload_entry(hass, config_entry)

    assert len(hass.data[DECONZ_DOMAIN]) == 1
    assert hass.data[DECONZ_DOMAIN][gateway2.bridgeid].master
