"""Test forecast solar energy platform."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.forecast_solar import energy
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_energy_solar_forecast(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test the Forecast.Solar energy platform solar forecast.

    The API keys each energy value by the end of its period: the first key
    of a day is sunrise with 0 Wh and the last one is sunset.
    """
    mock_forecast_solar.estimate.return_value.wh_period = {
        datetime(2026, 10, 24, 5, 41, tzinfo=UTC): 0,
        datetime(2026, 10, 24, 6, 0, tzinfo=UTC): 6,
        datetime(2026, 10, 24, 7, 0, tzinfo=UTC): 91,
        datetime(2026, 10, 24, 16, 0, tzinfo=UTC): 244,
        datetime(2026, 10, 24, 16, 17, tzinfo=UTC): 16,
        datetime(2026, 10, 25, 6, 43, tzinfo=UTC): 0,
        datetime(2026, 10, 25, 7, 0, tzinfo=UTC): 5,
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await energy.async_get_solar_forecast(hass, mock_config_entry.entry_id) == {
        "wh_hours": {
            "2026-10-24T05:41:00+00:00": 6,
            "2026-10-24T06:00:00+00:00": 91,
            "2026-10-24T07:00:00+00:00": 244,
            "2026-10-24T16:00:00+00:00": 16,
            "2026-10-24T16:17:00+00:00": 0,
            "2026-10-25T06:43:00+00:00": 5,
        }
    }


async def test_energy_solar_forecast_filters_midnight_utc_zeros(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_forecast_solar: MagicMock,
) -> None:
    """Test that artificial zero values at UTC midnight boundaries are filtered out.

    The zero at 00:00 starts a new API day: the energy of 23:00-00:00 is
    missing, not zero.
    """
    mock_forecast_solar.estimate.return_value.wh_period = {
        datetime(2026, 3, 25, 20, 2, 38, tzinfo=UTC): 0,
        datetime(2026, 3, 25, 21, 0, tzinfo=UTC): 123,
        datetime(2026, 3, 25, 22, 0, tzinfo=UTC): 346,
        datetime(2026, 3, 25, 23, 0, tzinfo=UTC): 502,
        datetime(2026, 3, 26, 0, 0, tzinfo=UTC): 0,
        datetime(2026, 3, 26, 1, 0, tzinfo=UTC): 718,
        datetime(2026, 3, 26, 2, 0, tzinfo=UTC): 766,
    }

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await energy.async_get_solar_forecast(hass, mock_config_entry.entry_id)
    assert result == {
        "wh_hours": {
            "2026-03-25T20:02:38+00:00": 123,
            "2026-03-25T21:00:00+00:00": 346,
            "2026-03-25T22:00:00+00:00": 502,
            "2026-03-26T00:00:00+00:00": 718,
            "2026-03-26T01:00:00+00:00": 766,
        }
    }


async def test_energy_solar_forecast_invalid_id(hass: HomeAssistant) -> None:
    """Test the Forecast.Solar energy platform with invalid config entry ID."""
    assert await energy.async_get_solar_forecast(hass, "invalid_id") is None
