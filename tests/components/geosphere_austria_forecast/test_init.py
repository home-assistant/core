"""Test the GeoSphere Austria Forecast integration setup."""

from datetime import timedelta
from unittest.mock import MagicMock, call

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from zamg import ZamgApiError, ZamgNoDataError

from homeassistant.components.geosphere_austria_forecast.const import (
    DOMAIN,
    SUBENTRY_TYPE_LOCATION,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import init_integration
from .conftest import SUBENTRY_ID

GRAZ = ConfigSubentry(
    data={CONF_LATITUDE: 47.07, CONF_LONGITUDE: 15.44},
    subentry_type=SUBENTRY_TYPE_LOCATION,
    title="Graz",
    unique_id="47.0700-15.4400",
)


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test the entry loads and unloads."""
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_nwp_client.request_timeout == 60

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ZamgApiError("Server error", status_code=500), id="api_error"),
        pytest.param(ZamgNoDataError("Invalid data"), id="no_data"),
    ],
)
async def test_setup_retries_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
    exception: Exception,
) -> None:
    """Test setup is retried when the forecast cannot be fetched."""
    mock_nwp_client.get_forecast.side_effect = exception
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_one_request_per_location_and_hour(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test each location is fetched with its coordinates once per hour."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_add_subentry(mock_config_entry, GRAZ)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_nwp_client.get_forecast.await_args_list == [
        call(latitude=48.2877, longitude=15.98486),
        call(latitude=47.07, longitude=15.44),
    ]

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_nwp_client.get_forecast.await_count == 4


async def test_added_location_gets_an_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test a location added after setup gets its own weather entity."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_all(Platform.WEATHER)) == 1

    hass.config_entries.async_add_subentry(mock_config_entry, GRAZ)
    await hass.async_block_till_done()
    assert len(hass.states.async_all(Platform.WEATHER)) == 2
    mock_nwp_client.get_forecast.assert_awaited_with(latitude=47.07, longitude=15.44)


@pytest.mark.usefixtures("mock_nwp_client")
async def test_removed_location_loses_its_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a location removes its device and weather entity."""
    await init_integration(hass, mock_config_entry)
    identifier = (DOMAIN, SUBENTRY_ID)
    entry_id = mock_config_entry.entry_id
    assert device_registry.async_get_device_by_identifier(identifier, entry_id)

    hass.config_entries.async_remove_subentry(mock_config_entry, SUBENTRY_ID)
    await hass.async_block_till_done()

    assert device_registry.async_get_device_by_identifier(identifier, entry_id) is None
    assert hass.states.async_all(Platform.WEATHER) == []
