"""Test the Ecowitt config flow."""
from homeassistant.components.ecowitt.const import (
    CONF_UNIT_WINDCHILL,
    SIGNAL_UPDATE,
    W_TYPE_HYBRID,
    W_TYPE_NEW,
    W_TYPE_OLD,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import TEST_DATA, _mock_ecowitt


async def test_setup_entry(hass: HomeAssistant):
    """Validate that setup entry also configure the client."""
    config_entry = await _mock_ecowitt(hass, TEST_DATA, {})

    assert config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_windchill(hass: HomeAssistant):
    """Validate that setup entry also configure the client."""
    for windc in [W_TYPE_NEW, W_TYPE_OLD, W_TYPE_HYBRID]:
        config_entry = await _mock_ecowitt(
            hass, TEST_DATA, {CONF_UNIT_WINDCHILL: windc}
        )

        assert config_entry.state == ConfigEntryState.LOADED


async def test_update_callback(hass: HomeAssistant):
    """Validate the callback for updates."""
    config_entry = await _mock_ecowitt(hass, TEST_DATA, {})
    async_dispatcher_send(hass, SIGNAL_UPDATE.format(config_entry.entry_id))
