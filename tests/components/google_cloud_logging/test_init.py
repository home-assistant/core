"""Tests for the Google Cloud Logging integration."""
from asynctest import Mock, patch
from google.cloud.logging import Client

from homeassistant.components.google_cloud_logging import DOMAIN
from homeassistant.setup import async_setup_component


async def test_async_setup_loads_credentials(hass, config):
    """Test component setup creates entry from config."""
    with patch.object(Client, "from_service_account_json", return_value=Mock()):
        assert not await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_async_setup_broken_credentials(hass, config):
    """Test component setup creates entry from config."""
    with patch.object(
        Client, "from_service_account_json", side_effect=ValueError("Error text")
    ):
        assert not await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
