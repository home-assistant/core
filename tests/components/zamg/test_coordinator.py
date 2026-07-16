"""Tests for the ZAMG data update coordinator."""

from unittest.mock import patch

import pytest
from zamg.exceptions import ZamgError, ZamgNoDataError

from homeassistant.components.zamg.coordinator import ZamgDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_async_update_data_sets_parameters_and_forecasts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator update with api_fields and forecast data."""
    with patch(
        "homeassistant.components.zamg.coordinator.ZamgDevice", autospec=True
    ) as zamg_device:
        zamg = zamg_device.return_value
        zamg.update.return_value = {"station": {"P": {"data": 1013.0}}}
        nowcast = {
            "t2m": 14.0,
            "rain": 0.0,
            "wind_speed": 5.0,
            "rh2m": 45.0,
            "tcc": 10.0,
        }
        forecast = {
            "timestamps": ["2026-01-01T13:00:00"],
            "features": [{"properties": {"parameters": {"t2m": {"data": [14.0]}}}}],
        }
        zamg.get_forecast.side_effect = [nowcast, forecast]
        zamg.last_update = "2026-01-01T12:00:00"
        zamg.get_station_name = "Graz/Flughafen"

        coordinator = ZamgDataUpdateCoordinator(hass, entry=mock_config_entry)
        coordinator.api_fields = ["P"]

        data = await coordinator._async_update_data()

    assert data["station"]["P"]["data"] == 1013.0
    zamg.set_parameters.assert_called_once_with(["P"])
    assert coordinator.data["nowcast"] == nowcast
    assert coordinator.data["forecast"] == forecast


async def test_async_update_data_handles_no_data_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator wraps no-data errors in UpdateFailed."""
    with patch(
        "homeassistant.components.zamg.coordinator.ZamgDevice", autospec=True
    ) as zamg_device:
        zamg = zamg_device.return_value
        zamg.update.side_effect = ZamgNoDataError("no data")
        coordinator = ZamgDataUpdateCoordinator(hass, entry=mock_config_entry)

        with pytest.raises(UpdateFailed, match="No response from API"):
            await coordinator._async_update_data()


async def test_async_update_data_handles_generic_zamg_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test coordinator wraps generic API errors in UpdateFailed."""
    with patch(
        "homeassistant.components.zamg.coordinator.ZamgDevice", autospec=True
    ) as zamg_device:
        zamg = zamg_device.return_value
        zamg.update.side_effect = ZamgError("bad payload")
        coordinator = ZamgDataUpdateCoordinator(hass, entry=mock_config_entry)

        with pytest.raises(
            UpdateFailed, match="Invalid response from API: bad payload"
        ):
            await coordinator._async_update_data()
