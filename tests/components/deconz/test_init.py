"""Test deCONZ component setup process."""
from unittest.mock import Mock, patch

import asyncio
import pytest

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components import deconz

from tests.common import mock_coro, MockConfigEntry

ENTRY1_HOST = "1.2.3.4"
ENTRY1_PORT = 80
ENTRY1_API_KEY = "1234567890ABCDEF"
ENTRY1_BRIDGEID = "12345ABC"

ENTRY2_HOST = "2.3.4.5"
ENTRY2_PORT = 80
ENTRY2_API_KEY = "1234567890ABCDEF"
ENTRY2_BRIDGEID = "23456DEF"


async def setup_entry(hass, entry):
    """Test that setup entry works."""
    with patch.object(
        deconz.DeconzGateway, "async_setup", return_value=mock_coro(True)
    ), patch.object(
        deconz.DeconzGateway,
        "async_update_device_registry",
        return_value=mock_coro(True),
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
    with patch("pydeconz.DeconzSession.async_load_parameters", side_effect=Exception):
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
        "pydeconz.DeconzSession.async_load_parameters", side_effect=asyncio.TimeoutError
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
        },
    )
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    with patch.object(
        deconz.DeconzGateway, "async_reset", return_value=mock_coro(True)
    ):
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
        },
    )
    entry2.add_to_hass(hass)

    await setup_entry(hass, entry)
    await setup_entry(hass, entry2)

    with patch.object(
        deconz.DeconzGateway, "async_reset", return_value=mock_coro(True)
    ):
        assert await deconz.async_unload_entry(hass, entry)

    assert ENTRY2_BRIDGEID in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN][ENTRY2_BRIDGEID].master
