"""Tests for polling measures."""
import datetime

import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

DUMMY_REQUEST_INFO = aiohttp.client.RequestInfo(
    url="http://example.com", method="GET", headers={}, real_url="http://example.com"
)

CONNECTION_EXCEPTIONS = [
    aiohttp.ClientConnectionError("Mock connection error"),
    aiohttp.ClientResponseError(DUMMY_REQUEST_INFO, [], message="Mock response error"),
]


async def async_setup_test_fixture(hass, mock_get_station, initial_value):
    """Create a dummy config entry for testing polling."""
    mock_get_station.return_value = initial_value

    entry = MockConfigEntry(
        version=1,
        domain="eafm",
        entry_id="VikingRecorder1234",
        data={"station": "L1234"},
        title="Viking Recorder",
        connection_class=config_entries.CONN_CLASS_CLOUD_PUSH,
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, "eafm", {})
    assert entry.state == config_entries.ENTRY_STATE_LOADED
    await hass.async_block_till_done()

    async def poll(value):
        mock_get_station.reset_mock(return_value=True, side_effect=True)

        if isinstance(value, Exception):
            mock_get_station.side_effect = value
        else:
            mock_get_station.return_value = value

        next_update = dt_util.utcnow() + datetime.timedelta(60 * 15)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    return entry, poll


async def test_reading_measures_not_list(hass, mock_get_station):
    """
    Test that a measure can be a dict not a list.

    E.g. https://environment.data.gov.uk/flood-monitoring/id/stations/751110
    """
    _ = await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": {
                "@id": "really-long-unique-id",
                "label": "York Viking Recorder - level-stage-i-15_min----",
                "qualifier": "Stage",
                "parameterName": "Water Level",
                "latestReading": {"value": 5},
                "stationReference": "L1234",
            },
        },
    )

    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"


async def test_reading_no_unit(hass, mock_get_station):
    """
    Test that a sensor functions even if its unit is not known.

    E.g. https://environment.data.gov.uk/flood-monitoring/id/stations/L0410
    """
    _ = await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 5},
                    "stationReference": "L1234",
                }
            ],
        },
    )

    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"


async def test_ignore_invalid_latest_reading(hass, mock_get_station):
    """
    Test that a sensor functions even if its unit is not known.

    E.g. https://environment.data.gov.uk/flood-monitoring/id/stations/L0410
    """
    _ = await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": "http://environment.data.gov.uk/flood-monitoring/data/readings/L0410-level-stage-i-15_min----/2017-02-22T10-30-00Z",
                    "stationReference": "L0410",
                },
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Other",
                    "latestReading": {"value": 5},
                    "stationReference": "L0411",
                },
            ],
        },
    )

    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state is None

    state = hass.states.get("sensor.my_station_other_stage")
    assert state.state == "5"


@pytest.mark.parametrize("exception", CONNECTION_EXCEPTIONS)
async def test_reading_unavailable(hass, mock_get_station, exception):
    """Test that a sensor is marked as unavailable if there is a connection error."""
    _, poll = await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 5},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                }
            ],
        },
    )
    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"

    await poll(exception)
    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "unavailable"


@pytest.mark.parametrize("exception", CONNECTION_EXCEPTIONS)
async def test_recover_from_failure(hass, mock_get_station, exception):
    """Test that a sensor recovers from failures."""
    _, poll = await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 5},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                }
            ],
        },
    )
    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"

    await poll(exception)
    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "unavailable"

    await poll(
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 56},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                }
            ],
        },
    )
    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "56"


async def test_reading_is_sampled(hass, mock_get_station):
    """Test that a sensor is added and polled."""
    await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 5},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                }
            ],
        },
    )

    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"
    assert state.attributes["unit_of_measurement"] == "m"


async def test_multiple_readings_are_sampled(hass, mock_get_station):
    """Test that multiple sensors are added and polled."""
    await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 5},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                },
                {
                    "@id": "really-long-unique-id-2",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Second Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 4},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                },
            ],
        },
    )

    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"
    assert state.attributes["unit_of_measurement"] == "m"

    state = hass.states.get("sensor.my_station_water_level_second_stage")
    assert state.state == "4"
    assert state.attributes["unit_of_measurement"] == "m"


async def test_ignore_no_latest_reading(hass, mock_get_station):
    """Test that a measure is ignored if it has no latest reading."""
    await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 5},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                },
                {
                    "@id": "really-long-unique-id-2",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Second Stage",
                    "parameterName": "Water Level",
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                },
            ],
        },
    )

    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"
    assert state.attributes["unit_of_measurement"] == "m"

    state = hass.states.get("sensor.my_station_water_level_second_stage")
    assert state is None


async def test_mark_existing_as_unavailable_if_no_latest(hass, mock_get_station):
    """Test that a measure is marked as unavailable if it has no latest reading."""
    _, poll = await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 5},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                }
            ],
        },
    )

    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"
    assert state.attributes["unit_of_measurement"] == "m"

    await poll(
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                }
            ],
        }
    )
    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "unavailable"

    await poll(
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 5},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                }
            ],
        }
    )
    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"


async def test_unload_entry(hass, mock_get_station):
    """Test being able to unload an entry."""
    entry, _ = await async_setup_test_fixture(
        hass,
        mock_get_station,
        {
            "label": "My station",
            "measures": [
                {
                    "@id": "really-long-unique-id",
                    "label": "York Viking Recorder - level-stage-i-15_min----",
                    "qualifier": "Stage",
                    "parameterName": "Water Level",
                    "latestReading": {"value": 5},
                    "stationReference": "L1234",
                    "unit": "http://qudt.org/1.1/vocab/unit#Meter",
                    "unitName": "m",
                }
            ],
        },
    )

    # And there should be an entity
    state = hass.states.get("sensor.my_station_water_level_stage")
    assert state.state == "5"

    assert await entry.async_unload(hass)

    # And the entity should be gone
    assert not hass.states.get("sensor.my_station_water_level_stage")
