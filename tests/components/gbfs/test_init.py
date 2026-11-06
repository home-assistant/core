"""Tests for setting up the GBFS integration."""

from types import MappingProxyType

from aiohttp import ClientError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.gbfs.const import (
    CONF_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import BASE_URL, STATION_SUBENTRY_ID, V3_URL, mock_feed


@pytest.mark.usefixtures("init_integration")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(V3_URL, id="discovery"),
        pytest.param(f"{BASE_URL}/v3/station_status.json", id="first_refresh"),
    ],
)
async def test_setup_retry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    url: str,
) -> None:
    """Test connection errors during setup retry later."""
    # Registered first, so it wins over the feed mock of the same URL.
    aioclient_mock.get(url, exc=ClientError())
    mock_feed(aioclient_mock, "v3")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_adding_station_reloads(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a new station subentry gets its sensors."""
    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data=MappingProxyType({CONF_STATION_ID: "s2"}),
            subentry_type=SUBENTRY_TYPE_STATION,
            title="Park Ave & 2nd St",
            unique_id="s2",
        ),
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.park_ave_2nd_st_vehicles_available").state == "1"


@pytest.mark.usefixtures("init_integration")
async def test_removing_station_drops_its_entities_and_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a station subentry reloads and drops only that station."""
    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data=MappingProxyType({CONF_STATION_ID: "s2"}),
            subentry_type=SUBENTRY_TYPE_STATION,
            title="Park Ave & 2nd St",
            unique_id="s2",
        ),
    )
    await hass.async_block_till_done()
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "example_bikes_s1"), mock_config_entry.entry_id
    )

    hass.config_entries.async_remove_subentry(mock_config_entry, STATION_SUBENTRY_ID)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.main_st_1st_ave_vehicles_available") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "example_bikes_s1"), mock_config_entry.entry_id
        )
        is None
    )
    assert hass.states.get("sensor.park_ave_2nd_st_vehicles_available") is not None
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "example_bikes_s2"), mock_config_entry.entry_id
    )
