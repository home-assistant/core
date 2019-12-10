"""Test deCONZ component setup process."""
import asyncio

from asynctest import Mock, patch
import pytest

from homeassistant.components import deconz
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry

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
    entry = Mock()
    entry.data = {
        deconz.config_flow.CONF_HOST: ENTRY1_HOST,
        deconz.config_flow.CONF_PORT: ENTRY1_PORT,
        deconz.config_flow.CONF_API_KEY: ENTRY1_API_KEY,
    }
    with patch("pydeconz.DeconzSession.initialize", side_effect=Exception):
        await deconz.async_setup_entry(hass, entry)


async def test_setup_entry_no_available_bridge(hass):
    """Test setup entry fails if deCONZ is not available."""
    entry = Mock()
    entry.data = {
        deconz.config_flow.CONF_HOST: ENTRY1_HOST,
        deconz.config_flow.CONF_PORT: ENTRY1_PORT,
        deconz.config_flow.CONF_API_KEY: ENTRY1_API_KEY,
    }
    with patch(
        "pydeconz.DeconzSession.initialize", side_effect=asyncio.TimeoutError
    ), pytest.raises(ConfigEntryNotReady):
        await deconz.async_setup_entry(hass, entry)


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    entry = MockConfigEntry(
        domain=deconz.DOMAIN,
        data={
            deconz.config_flow.CONF_HOST: ENTRY1_HOST,
            deconz.config_flow.CONF_PORT: ENTRY1_PORT,
            deconz.config_flow.CONF_API_KEY: ENTRY1_API_KEY,
            deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID,
            deconz.CONF_UUID: ENTRY1_UUID,
        },
    )
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    assert ENTRY1_BRIDGEID in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN][ENTRY1_BRIDGEID].master


async def test_setup_entry_multiple_gateways(hass):
    """Test setup entry is successful with multiple gateways."""
    entry = MockConfigEntry(
        domain=deconz.DOMAIN,
        data={
            deconz.config_flow.CONF_HOST: ENTRY1_HOST,
            deconz.config_flow.CONF_PORT: ENTRY1_PORT,
            deconz.config_flow.CONF_API_KEY: ENTRY1_API_KEY,
            deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID,
            deconz.CONF_UUID: ENTRY1_UUID,
        },
    )
    entry.add_to_hass(hass)

    entry2 = MockConfigEntry(
        domain=deconz.DOMAIN,
        data={
            deconz.config_flow.CONF_HOST: ENTRY2_HOST,
            deconz.config_flow.CONF_PORT: ENTRY2_PORT,
            deconz.config_flow.CONF_API_KEY: ENTRY2_API_KEY,
            deconz.CONF_BRIDGEID: ENTRY2_BRIDGEID,
            deconz.CONF_UUID: ENTRY2_UUID,
        },
    )
    entry2.add_to_hass(hass)

    await setup_entry(hass, entry)
    await setup_entry(hass, entry2)

    assert ENTRY1_BRIDGEID in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN][ENTRY1_BRIDGEID].master
    assert ENTRY2_BRIDGEID in hass.data[deconz.DOMAIN]
    assert not hass.data[deconz.DOMAIN][ENTRY2_BRIDGEID].master


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=deconz.DOMAIN,
        data={
            deconz.config_flow.CONF_HOST: ENTRY1_HOST,
            deconz.config_flow.CONF_PORT: ENTRY1_PORT,
            deconz.config_flow.CONF_API_KEY: ENTRY1_API_KEY,
            deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID,
            deconz.CONF_UUID: ENTRY1_UUID,
        },
    )
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    with patch.object(deconz.DeconzGateway, "async_reset", return_value=True):
        assert await deconz.async_unload_entry(hass, entry)

    assert not hass.data[deconz.DOMAIN]


async def test_unload_entry_multiple_gateways(hass):
    """Test being able to unload an entry and master gateway gets moved."""
    entry = MockConfigEntry(
        domain=deconz.DOMAIN,
        data={
            deconz.config_flow.CONF_HOST: ENTRY1_HOST,
            deconz.config_flow.CONF_PORT: ENTRY1_PORT,
            deconz.config_flow.CONF_API_KEY: ENTRY1_API_KEY,
            deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID,
            deconz.CONF_UUID: ENTRY1_UUID,
        },
    )
    entry.add_to_hass(hass)

    entry2 = MockConfigEntry(
        domain=deconz.DOMAIN,
        data={
            deconz.config_flow.CONF_HOST: ENTRY2_HOST,
            deconz.config_flow.CONF_PORT: ENTRY2_PORT,
            deconz.config_flow.CONF_API_KEY: ENTRY2_API_KEY,
            deconz.CONF_BRIDGEID: ENTRY2_BRIDGEID,
            deconz.CONF_UUID: ENTRY2_UUID,
        },
    )
    entry2.add_to_hass(hass)

    await setup_entry(hass, entry)
    await setup_entry(hass, entry2)

    with patch.object(deconz.DeconzGateway, "async_reset", return_value=True):
        assert await deconz.async_unload_entry(hass, entry)

    assert ENTRY2_BRIDGEID in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN][ENTRY2_BRIDGEID].master
