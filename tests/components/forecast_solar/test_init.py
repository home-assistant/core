"""Tests for the Forecast.Solar integration."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from forecast_solar import ForecastSolarConnectionError

from homeassistant.components.forecast_solar.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_forecast_solar: MagicMock,
    hass_ws_client,
) -> None:
    """Test the Forecast.Solar configuration entry loading/unloading."""
    mock_forecast_solar.estimate.return_value.watts = {
        datetime(2021, 6, 27, 13, 0, tzinfo=timezone.utc): 12,
        datetime(2021, 6, 27, 14, 0, tzinfo=timezone.utc): 8,
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Test WS API set up
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 5,
            "type": "forecast_solar/forecasts",
        }
    )
    result = await client.receive_json()
    assert result["success"]
    assert result["result"] == {
        mock_config_entry.entry_id: {
            "2021-06-27T13:00:00+00:00": 12,
            "2021-06-27T14:00:00+00:00": 8,
        }
    }

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)


@patch(
    "homeassistant.components.forecast_solar.ForecastSolar.estimate",
    side_effect=ForecastSolarConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Forecast.Solar configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
