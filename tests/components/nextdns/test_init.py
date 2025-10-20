"""Test init of NextDNS integration."""

from unittest.mock import AsyncMock, patch

from nextdns import ApiError, InvalidApiKeyError
import pytest
from tenacity import RetryError

from homeassistant.components.nextdns.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.fake_profile_dns_queries_blocked_ratio")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "20.0"


@pytest.mark.parametrize(
    "exc", [ApiError("API Error"), RetryError("Retry Error"), TimeoutError]
)
async def test_config_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, exc: Exception
) -> None:
    """Test for setup failure if the connection to the service fails."""
    with patch(
        "homeassistant.components.nextdns.NextDns.create",
        side_effect=exc,
    ):
        await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test successful unload of entry."""
    await init_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_config_auth_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test for setup failure if the auth fails."""
    with patch(
        "homeassistant.components.nextdns.NextDns.create",
        side_effect=InvalidApiKeyError,
    ):
        await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id
