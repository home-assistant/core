"""Tests for the google_wifi component setup."""

from unittest.mock import patch

from homeassistant.components.google_wifi import async_setup
from homeassistant.components.google_wifi.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_and_unload(hass: HomeAssistant) -> None:
    """Test setup and unload lifecycle."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.86.1", CONF_NAME: "Google Wifi"},
        entry_id="test_123",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.google_wifi.sensor.requests.get"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN]["test_123"] == entry.data

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert "test_123" not in hass.data[DOMAIN]


async def test_setup_yaml_import(hass: HomeAssistant) -> None:
    """Test that YAML config triggers the import flow."""
    config = {DOMAIN: [{CONF_IP_ADDRESS: "192.168.86.1", CONF_NAME: "Legacy"}]}

    # Use the proper class path for patching the flow manager
    with patch(
        "homeassistant.config_entries.ConfigEntriesFlowManager.async_init"
    ) as mock_init:
        assert await async_setup(hass, config) is True
        await hass.async_block_till_done()
        mock_init.assert_called_once()
