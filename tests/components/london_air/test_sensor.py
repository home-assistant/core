"""The tests for the london_air platform."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pylondonair import (
    NO_SPECIES_DATA,
    LondonAirConnectionError,
    LondonAirData,
    LondonAirUpdateError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.london_air.const import (
    CONF_LOCATIONS,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("setup_entry")
async def test_valid_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for operational london_air sensor with proper attributes."""
    state = hass.states.get("sensor.merton_air_quality")
    assert state is not None
    assert state.state == "Low"
    assert state.attributes["icon"] == "mdi:cloud-outline"
    assert state.attributes["updated"] == "2017-08-03 03:00:00"
    assert state.attributes["sites"] == 2
    assert state.attributes["friendly_name"] == "Merton Air Quality"

    entity_entry = entity_registry.async_get("sensor.merton_air_quality")
    assert entity_entry is not None
    assert entity_entry.unique_id == "Merton"
    assert entity_entry.device_id is not None

    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None
    assert device_entry.entry_type is DeviceEntryType.SERVICE
    assert device_entry.name == "Merton"
    assert device_entry.manufacturer == "Imperial College London"
    assert (DOMAIN, "Merton") in device_entry.identifiers

    sites = state.attributes["data"]
    assert sites is not None
    assert len(sites) == 2
    assert sites[0]["site_code"] == "ME2"
    assert sites[0]["site_type"] == "Roadside"
    assert sites[0]["site_name"] == "Merton Road"
    assert sites[0]["pollutants_status"] == "Low"

    pollutants = sites[0]["pollutants"]
    assert pollutants is not None
    assert len(pollutants) == 1
    assert pollutants[0]["code"] == "PM10"
    assert pollutants[0]["quality"] == "Low"
    assert int(pollutants[0]["index"]) == 2
    assert pollutants[0]["summary"] == "PM10 is Low"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            LondonAirConnectionError("Request to London Air API failed"),
            id="connection-error",
        ),
        pytest.param(
            LondonAirUpdateError("Invalid JSON from London Air API"),
            id="update-error",
        ),
    ],
)
async def test_api_failure(
    hass: HomeAssistant,
    error: LondonAirConnectionError | LondonAirUpdateError,
    locations: list[str],
    mock_london_air_client: AsyncMock,
) -> None:
    """Test that a failed first refresh leaves the entry in setup retry."""
    mock_london_air_client.async_update.side_effect = error
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_LOCATIONS: locations},
        title="London Air",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get("sensor.merton_air_quality") is None


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            LondonAirConnectionError("Request to London Air API failed"),
            id="connection-error",
        ),
        pytest.param(
            LondonAirUpdateError("Invalid JSON from London Air API"),
            id="update-error",
        ),
    ],
)
async def test_update_failure_keeps_last_data(
    hass: HomeAssistant,
    error: LondonAirConnectionError | LondonAirUpdateError,
    setup_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test that a failed update keeps the last good data."""
    state = hass.states.get("sensor.merton_air_quality")
    assert state is not None
    assert state.state == "Low"

    mock_london_air_client.async_update.side_effect = error
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # A failed update marks the entity unavailable but keeps the last good data
    state = hass.states.get("sensor.merton_air_quality")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert setup_entry.runtime_data.data is not None


@pytest.mark.parametrize(
    ("locations", "entity_id"),
    [
        pytest.param(
            ["City of London"],
            "sensor.city_of_london_air_quality",
            id="authority-without-sites",
        ),
        pytest.param(
            ["Barking and Dagenham"],
            "sensor.barking_and_dagenham_air_quality",
            id="authority-not-in-data",
        ),
    ],
)
@pytest.mark.usefixtures("setup_entry")
async def test_authority_without_site_data(hass: HomeAssistant, entity_id: str) -> None:
    """Test an authority with no usable site data."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["updated"] is None
    assert state.attributes["sites"] == 0


@pytest.mark.parametrize("locations", [pytest.param(["Barnet"], id="barnet")])
@pytest.mark.usefixtures("setup_entry")
async def test_site_without_pollutants(hass: HomeAssistant) -> None:
    """Test a site that reports no pollutant data."""
    state = hass.states.get("sensor.barnet_air_quality")
    assert state is not None
    assert state.state == "Low"
    site = state.attributes["data"][0]
    assert site["pollutants"] == [NO_SPECIES_DATA]
    assert site["pollutants_status"] == "no_species_data"
    assert site["number_of_pollutants"] == 0


@pytest.mark.usefixtures("setup_entry")
async def test_update_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test that the coordinator polls at the configured interval."""
    assert mock_london_air_client.async_update.await_count == 1
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_london_air_client.async_update.await_count == 2


async def test_multiple_yaml_blocks_merge_locations(
    hass: HomeAssistant,
    london_air_data: LondonAirData,
    mock_london_air_client: AsyncMock,
) -> None:
    """Test that multiple YAML blocks merge their locations into one entry."""
    mock_london_air_client.async_update.return_value = london_air_data
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {"platform": "london_air", "locations": ["Merton"]},
                {"platform": "london_air", "locations": ["Barnet"]},
            ]
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert set(entries[0].data[CONF_LOCATIONS]) == {"Merton", "Barnet"}

    assert hass.states.get("sensor.merton_air_quality") is not None
    assert hass.states.get("sensor.barnet_air_quality") is not None
