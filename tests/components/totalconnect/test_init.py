"""Tests for the TotalConnect init process."""

from unittest.mock import patch

from total_connect_client.exceptions import AuthenticationError

from homeassistant.components.totalconnect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import CONFIG_DATA

from tests.common import MockConfigEntry


async def test_reauth_started(hass: HomeAssistant) -> None:
    """Test that reauth is started when we have login errors."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient",
    ) as mock_client:
        mock_client.side_effect = AuthenticationError()
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_ERROR
