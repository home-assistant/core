"""Test the Ecowitt config flow."""
import logging
from unittest.mock import patch

from homeassistant.components.ecowitt.const import (
    CONF_UNIT_WINDCHILL,
    DOMAIN as ECOWITT_DOMAIN,
    SIGNAL_UPDATE,
    W_TYPE_HYBRID,
    W_TYPE_NEW,
    W_TYPE_OLD,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import EcoWittListenerMock

from tests.common import MockConfigEntry

TEST_DATA = {CONF_PORT: 4199}

_LOGGER = logging.getLogger(__name__)


async def test_setup_entry(hass: HomeAssistant):
    """Validate that setup entry also configure the client."""
    config_entry = await _setup_full_mock(hass, TEST_DATA, {})

    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_windchill(hass: HomeAssistant):
    """Validate that setup entry also configure the client."""
    for windc in [W_TYPE_NEW, W_TYPE_OLD, W_TYPE_HYBRID]:
        config_entry = await _setup_full_mock(
            hass, TEST_DATA, {CONF_UNIT_WINDCHILL: windc}
        )

        assert config_entry.state == ConfigEntryState.LOADED


async def test_update_callback(hass: HomeAssistant):
    """Validate the callback for updates."""
    config_entry = await _setup_full_mock(hass, TEST_DATA, {})
    async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))


async def _setup_full_mock(hass: HomeAssistant, data_mock, options):
    """Set up a fully mocked library."""
    config_entry = MockConfigEntry(domain=ECOWITT_DOMAIN, data=data_mock)
    config_entry.options = options
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ecowitt.EcoWittListener", new=EcoWittListenerMock
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
