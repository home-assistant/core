"""Tests for the Google Cloud integration."""

from homeassistant import config_entries
from homeassistant.components.google_cloud.const import (
    CONF_SERVICE_ACCOUNT_INFO,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Test setup raises ConfigEntryAuthFailed when service account info is invalid."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SERVICE_ACCOUNT_INFO: {}},
        state=config_entries.ConfigEntryState.NOT_LOADED,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR
    mock_config_entry.async_get_active_flows(hass, {"reauth"})
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))
