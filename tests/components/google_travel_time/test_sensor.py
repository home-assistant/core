"""Test the Google Maps Travel Time sensors."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.google_travel_time.config_flow import default_options
from homeassistant.components.google_travel_time.const import (
    CONF_ARRIVAL_TIME,
    CONF_DEPARTURE_TIME,
    DOMAIN,
    UNITS_IMPERIAL,
    UNITS_METRIC,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_update")
def mock_update_fixture() -> Generator[MagicMock]:
    """Mock an update to the sensor."""
    with (
        patch("homeassistant.components.google_travel_time.sensor.Client"),
        patch(
            "homeassistant.components.google_travel_time.sensor.distance_matrix"
        ) as distance_matrix_mock,
    ):
        distance_matrix_mock.return_value = {
            "rows": [
                {
                    "elements": [
                        {
                            "duration_in_traffic": {
                                "value": 1620,
                                "text": "27 mins",
                            },
                            "duration": {
                                "value": 1560,
                                "text": "26 mins",
                            },
                            "distance": {"text": "21.3 km"},
                        }
                    ]
                }
            ]
        }
        yield distance_matrix_mock


@pytest.fixture(name="mock_update_duration")
def mock_update_duration_fixture(mock_update: MagicMock) -> MagicMock:
    """Mock an update to the sensor returning no duration_in_traffic."""
    mock_update.return_value = {
        "rows": [
            {
                "elements": [
                    {
                        "duration": {
                            "value": 1560,
                            "text": "26 mins",
                        },
                        "distance": {"text": "21.3 km"},
                    }
                ]
            }
        ]
    }
    return mock_update


@pytest.fixture(name="mock_update_empty")
def mock_update_empty_fixture(mock_update: MagicMock) -> MagicMock:
    """Mock an update to the sensor with an empty response."""
    mock_update.return_value = None
    return mock_update


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, {})],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor(hass: HomeAssistant) -> None:
    """Test that sensor works."""
    assert hass.states.get("sensor.google_travel_time").state == "27"
    assert (
        hass.states.get("sensor.google_travel_time").attributes["attribution"]
        == "Powered by Google"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["duration"] == "26 mins"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["duration_in_traffic"]
        == "27 mins"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["distance"] == "21.3 km"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["origin"] == "location1"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["destination"]
        == "location2"
    )
    assert (
        hass.states.get("sensor.google_travel_time").attributes["unit_of_measurement"]
        == "min"
    )


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, {})],
)
@pytest.mark.usefixtures("mock_update_duration", "mock_config")
async def test_sensor_duration(hass: HomeAssistant) -> None:
    """Test that sensor works with no duration_in_traffic in response."""
    assert hass.states.get("sensor.google_travel_time").state == "26"


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, {})],
)
@pytest.mark.usefixtures("mock_update_empty", "mock_config")
async def test_sensor_empty_response(hass: HomeAssistant) -> None:
    """Test that sensor works for an empty response."""
    assert hass.states.get("sensor.google_travel_time").state == "unknown"


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_DEPARTURE_TIME: "10:00",
            },
        ),
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor_departure_time(hass: HomeAssistant) -> None:
    """Test that sensor works for departure time."""
    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_DEPARTURE_TIME: "custom_timestamp",
            },
        ),
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor_departure_time_custom_timestamp(hass: HomeAssistant) -> None:
    """Test that sensor works for departure time with a custom timestamp."""
    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_ARRIVAL_TIME: "10:00",
            },
        ),
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor_arrival_time(hass: HomeAssistant) -> None:
    """Test that sensor works for arrival time."""
    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_ARRIVAL_TIME: "custom_timestamp",
            },
        ),
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor_arrival_time_custom_timestamp(hass: HomeAssistant) -> None:
    """Test that sensor works for arrival time with a custom timestamp."""
    assert hass.states.get("sensor.google_travel_time").state == "27"


@pytest.mark.parametrize(
    ("unit_system", "expected_unit_option"),
    [
        (METRIC_SYSTEM, UNITS_METRIC),
        (US_CUSTOMARY_SYSTEM, UNITS_IMPERIAL),
    ],
)
async def test_sensor_unit_system(
    hass: HomeAssistant,
    unit_system: UnitSystem,
    expected_unit_option: str,
) -> None:
    """Test that sensor works."""
    hass.config.units = unit_system

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        options=default_options(hass),
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.google_travel_time.sensor.Client"),
        patch(
            "homeassistant.components.google_travel_time.sensor.distance_matrix"
        ) as distance_matrix_mock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    distance_matrix_mock.assert_called_once()
    assert distance_matrix_mock.call_args.kwargs["units"] == expected_unit_option
