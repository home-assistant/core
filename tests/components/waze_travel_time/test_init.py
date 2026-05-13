"""Test waze_travel_time services."""

import pytest

from homeassistant.components.waze_travel_time.const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_BASE_COORDINATES,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_REALTIME,
    CONF_TIME_DELTA,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_AVOID_FERRIES,
    DEFAULT_AVOID_SUBSCRIPTION_ROADS,
    DEFAULT_AVOID_TOLL_ROADS,
    DEFAULT_FILTER,
    DEFAULT_OPTIONS,
    DEFAULT_REALTIME,
    DEFAULT_TIME_DELTA,
    DEFAULT_VEHICLE_TYPE,
    DOMAIN,
    METRIC_UNITS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_REGION
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


async def call_service_get_travel_times(
    hass: HomeAssistant,
    origin: str,
    destination: str,
    vehicle_type: str,
    region: str,
    units: str,
    incl_filter: list[str] | None = None,
    time_delta: dict[str, int] | None = None,
    base_coordinates: dict[str, float] | None = None,
) -> dict:
    """Call the get_travel_times service."""
    params = {
        "origin": origin,
        "destination": destination,
        "vehicle_type": vehicle_type,
        "region": region,
        "units": units,
        "incl_filter": incl_filter or [],
        "time_delta": time_delta or {},
    }
    if base_coordinates is not None:
        params["base_coordinates"] = base_coordinates
    return await hass.services.async_call(
        "waze_travel_time",
        "get_travel_times",
        params,
        blocking=True,
        return_response=True,
    )


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.parametrize(
    ("time_delta", "expected_time_delta", "base_coordinates", "expected_base_coords"),
    [
        pytest.param({"hours": 1, "minutes": 30}, 90, None, None, id="positive"),
        pytest.param(
            {"hours": -1, "minutes": -30},
            -90,
            {CONF_LATITUDE: 40.7128, CONF_LONGITUDE: -74.0060},
            (
                40.7128,
                -74.0060,
            ),
            id="negative_with_base_coordinates",
        ),
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_service_get_travel_times(
    hass: HomeAssistant,
    mock_update,
    time_delta: dict[str, int],
    expected_time_delta: int,
    base_coordinates: dict[str, float] | None,
    expected_base_coords: tuple[float, float] | None,
) -> None:
    """Test service get_travel_times."""
    response_data = await call_service_get_travel_times(
        hass,
        origin="location1",
        destination="location2",
        vehicle_type="car",
        region="us",
        units="imperial",
        incl_filter=["IncludeThis"],
        time_delta=time_delta,
        base_coordinates=base_coordinates,
    )
    assert response_data == {
        "routes": [
            {
                "distance": pytest.approx(186.4113),
                "duration": 150,
                "name": "E1337 - Teststreet",
                "street_names": ["E1337", "IncludeThis", "Teststreet"],
            },
        ]
    }
    assert mock_update.call_args_list[-1].kwargs["time_delta"] == expected_time_delta
    assert mock_update.call_args_list[-1].kwargs["base_coords"] == expected_base_coords


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_service_get_travel_times_empty_response(
    hass: HomeAssistant, mock_update
) -> None:
    """Test service get_travel_times."""
    mock_update.return_value = []
    response_data = await hass.services.async_call(
        "waze_travel_time",
        "get_travel_times",
        {
            "origin": "location1",
            "destination": "location2",
            "vehicle_type": "car",
            "region": "us",
            "units": "imperial",
            "incl_filter": ["IncludeThis"],
        },
        blocking=True,
        return_response=True,
    )
    assert response_data == {"routes": []}


@pytest.mark.usefixtures("mock_update")
async def test_migrate_entry_v1_to_v2_3(hass: HomeAssistant) -> None:
    """Test successful migration of entry data from v1 to v2.3."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_CONFIG,
        options={
            CONF_REALTIME: DEFAULT_REALTIME,
            CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
            CONF_UNITS: METRIC_UNITS,
            CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
            CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
        },
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 2
    assert updated_entry.minor_version == 3
    assert updated_entry.options[CONF_INCL_FILTER] == DEFAULT_FILTER
    assert updated_entry.options[CONF_EXCL_FILTER] == DEFAULT_FILTER
    assert updated_entry.options[CONF_TIME_DELTA] == DEFAULT_TIME_DELTA
    assert updated_entry.options[CONF_BASE_COORDINATES] == {
        CONF_LATITUDE: 40.713,
        CONF_LONGITUDE: -74.006,
    }

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_CONFIG,
        options={
            CONF_REALTIME: DEFAULT_REALTIME,
            CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
            CONF_UNITS: METRIC_UNITS,
            CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
            CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
            CONF_INCL_FILTER: "IncludeThis",
            CONF_EXCL_FILTER: "ExcludeThis",
        },
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 2
    assert updated_entry.minor_version == 3
    assert updated_entry.options[CONF_INCL_FILTER] == ["IncludeThis"]
    assert updated_entry.options[CONF_EXCL_FILTER] == ["ExcludeThis"]
    assert updated_entry.options[CONF_TIME_DELTA] == DEFAULT_TIME_DELTA
    assert updated_entry.options[CONF_BASE_COORDINATES] == {
        CONF_LATITUDE: 40.713,
        CONF_LONGITUDE: -74.006,
    }


@pytest.mark.usefixtures("mock_update")
async def test_migrate_entry_v2_1_to_v2_3(hass: HomeAssistant) -> None:
    """Test successful migration of entry from version 2.1 to 2.3."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        data=MOCK_CONFIG,
        options={
            CONF_REALTIME: DEFAULT_REALTIME,
            CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
            CONF_UNITS: METRIC_UNITS,
            CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
            CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
            CONF_INCL_FILTER: DEFAULT_FILTER,
            CONF_EXCL_FILTER: DEFAULT_FILTER,
        },
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 2
    assert updated_entry.minor_version == 3
    assert updated_entry.options[CONF_TIME_DELTA] == DEFAULT_TIME_DELTA
    assert updated_entry.options[CONF_BASE_COORDINATES] == {
        CONF_LATITUDE: 40.713,
        CONF_LONGITUDE: -74.006,
    }


@pytest.mark.parametrize(
    ("region", "expected_base_coordinates"),
    [
        pytest.param(
            "US",
            {CONF_LATITUDE: 40.713, CONF_LONGITUDE: -74.006},
            id="us",
        ),
        pytest.param(
            "NA",
            {CONF_LATITUDE: 40.713, CONF_LONGITUDE: -74.006},
            id="na",
        ),
        pytest.param(
            "EU",
            {CONF_LATITUDE: 47.498, CONF_LONGITUDE: 19.040},
            id="eu",
        ),
        pytest.param(
            "IL",
            {CONF_LATITUDE: 31.768, CONF_LONGITUDE: 35.214},
            id="il",
        ),
        pytest.param(
            "AU",
            {CONF_LATITUDE: -35.281, CONF_LONGITUDE: 149.128},
            id="au",
        ),
    ],
)
@pytest.mark.usefixtures("mock_update")
async def test_migrate_entry_v2_2_to_v2_3_adds_region_base_coordinates(
    hass: HomeAssistant,
    region: str,
    expected_base_coordinates: dict[str, float],
) -> None:
    """Test migration adds pywaze's default base coordinates for each region."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        data={**MOCK_CONFIG, CONF_REGION: region},
        options={
            CONF_REALTIME: DEFAULT_REALTIME,
            CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
            CONF_UNITS: METRIC_UNITS,
            CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
            CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
            CONF_INCL_FILTER: DEFAULT_FILTER,
            CONF_EXCL_FILTER: DEFAULT_FILTER,
            CONF_TIME_DELTA: DEFAULT_TIME_DELTA,
        },
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 2
    assert updated_entry.minor_version == 3
    assert updated_entry.options[CONF_BASE_COORDINATES] == expected_base_coordinates


@pytest.mark.usefixtures("mock_update")
async def test_migrate_entry_v2_2_to_v2_3_preserves_existing_base_coordinates(
    hass: HomeAssistant,
) -> None:
    """Test migration preserves configured base coordinates."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=2,
        data=MOCK_CONFIG,
        options={
            CONF_REALTIME: DEFAULT_REALTIME,
            CONF_VEHICLE_TYPE: DEFAULT_VEHICLE_TYPE,
            CONF_UNITS: METRIC_UNITS,
            CONF_AVOID_FERRIES: DEFAULT_AVOID_FERRIES,
            CONF_AVOID_SUBSCRIPTION_ROADS: DEFAULT_AVOID_SUBSCRIPTION_ROADS,
            CONF_AVOID_TOLL_ROADS: DEFAULT_AVOID_TOLL_ROADS,
            CONF_INCL_FILTER: DEFAULT_FILTER,
            CONF_EXCL_FILTER: DEFAULT_FILTER,
            CONF_TIME_DELTA: DEFAULT_TIME_DELTA,
            CONF_BASE_COORDINATES: {
                CONF_LATITUDE: 1.23,
                CONF_LONGITUDE: 4.56,
            },
        },
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)

    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 2
    assert updated_entry.minor_version == 3
    assert updated_entry.options[CONF_BASE_COORDINATES] == {
        CONF_LATITUDE: 1.23,
        CONF_LONGITUDE: 4.56,
    }
