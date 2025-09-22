"""Tests for AccuWeather coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from accuweather import InvalidApiKeyError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.accuweather.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import async_fire_time_changed


async def test_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_accuweather_client: AsyncMock,
) -> None:
    """Test authentication error when polling data."""
    mock_config_entry = await init_integration(hass)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_accuweather_client.async_get_current_conditions.side_effect = (
        InvalidApiKeyError("Invalid API Key")
    )
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
