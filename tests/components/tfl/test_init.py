"""Tests for the Transport for London integration."""

from unittest.mock import MagicMock, patch
from urllib.error import URLError

from tflwrapper import stopPoint

from homeassistant.components.tfl.const import (
    CONF_API_APP_KEY,
    CONF_STOP_POINTS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_DATA_TFL_STATION_ARRIVALS

from tests.common import MockConfigEntry


@patch("homeassistant.components.tfl.stopPoint")
async def test_async_setup_entry_success(
    m_stopPoint,
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a successful setup entry."""
    data = {
        CONF_API_APP_KEY: "appy_appy_app_key",
        CONF_STOP_POINTS: ["AAAAAAAA1"],
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="unique_id", data=data, options=data
    )

    stop_point_api: stopPoint = MagicMock()
    stop_point_api.getCategories = MagicMock(return_value={})
    stop_point_api.getStationArrivals = MagicMock(
        return_value=MOCK_DATA_TFL_STATION_ARRIVALS
    )
    stop_point_api.getByIDs = MagicMock(return_value={"commonName": "Test Stop Name"})
    m_stopPoint.return_value = stop_point_api

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data == data
    assert config_entry.options == data

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, config_entry.unique_id)}
    )
    assert device_entry is not None


async def test_config_not_ready_when_connection_failure(hass: HomeAssistant) -> None:
    """Test for setup failure if connection to TfL does not succeed."""

    data = {
        CONF_API_APP_KEY: "appy_appy_app_key",
        CONF_STOP_POINTS: ["AAAAAAAA1"],
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="unique_id", data=data, options=data
    )

    with patch(
        "homeassistant.components.tfl.stopPoint.getCategories",
        side_effect=URLError("A URL Connection Error"),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        assert config_entry.data == data
        assert config_entry.options == data
