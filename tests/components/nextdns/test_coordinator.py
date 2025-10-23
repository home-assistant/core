"""Tests for NextDNS coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from nextdns import InvalidApiKeyError

from homeassistant.components.nextdns.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
    mock_nextdns: AsyncMock,
) -> None:
    """Test authentication error when polling data."""
    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_nextdns_client.get_profiles.side_effect = InvalidApiKeyError
    mock_nextdns_client.get_analytics_status.side_effect = InvalidApiKeyError
    mock_nextdns_client.get_analytics_dnssec.side_effect = InvalidApiKeyError
    mock_nextdns_client.get_analytics_encryption.side_effect = InvalidApiKeyError
    mock_nextdns_client.get_analytics_ip_versions.side_effect = InvalidApiKeyError
    mock_nextdns_client.get_analytics_protocols.side_effect = InvalidApiKeyError
    mock_nextdns_client.get_settings.side_effect = InvalidApiKeyError
    mock_nextdns_client.connection_status.side_effect = InvalidApiKeyError

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id
