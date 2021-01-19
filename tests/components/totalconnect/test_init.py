"""Tests for the TotalConnect init process."""
from unittest.mock import patch

from homeassistant.components.totalconnect.const import DOMAIN
from homeassistant.setup import async_setup_component

from .common import CONFIG_DATA

from tests.common import MockConfigEntry


async def test_reauth_started(hass):
    """Test that reauth is started when we have login errors."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient",
        autospec=True,
    ) as mock_client, patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectConfigFlow.async_step_reauth"
    ) as mock_async_step_reauth:
        mock_client.return_value.is_valid_credentials.return_value = False
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
    mock_client.assert_called_once()
    mock_async_step_reauth.assert_called_once()
