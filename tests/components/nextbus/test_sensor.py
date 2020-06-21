"""The tests for the nexbus sensor component."""
from copy import deepcopy

import pytest

import homeassistant.components.nextbus.sensor as nextbus
import homeassistant.components.sensor as sensor

from tests.async_mock import patch
from tests.common import assert_setup_component, async_setup_component

VALID_AGENCY = "sf-muni"
VALID_ROUTE = "F"
VALID_STOP = "5650"
VALID_AGENCY_TITLE = "San Francisco Muni"
VALID_ROUTE_TITLE = "F-Market & Wharves"
VALID_STOP_TITLE = "Market St & 7th St"
SENSOR_ID_SHORT = "sensor.sf_muni_f"

CONFIG_BASIC = {
    "sensor": {
        "platform": "nextbus",
        "agency": VALID_AGENCY,
        "route": VALID_ROUTE,
        "stop": VALID_STOP,
    }
}

CONFIG_INVALID_MISSING = {"sensor": {"platform": "nextbus"}}

BASIC_RESULTS = {
    "predictions": {
        "agencyTitle": VALID_AGENCY_TITLE,
        "routeTitle": VALID_ROUTE_TITLE,
        "stopTitle": VALID_STOP_TITLE,
        "direction": {
            "title": "Outbound",
            "prediction": [
                {"minutes": "1", "epochTime": "1553807371000"},
                {"minutes": "2", "epochTime": "1553807372000"},
                {"minutes": "3", "epochTime": "1553807373000"},
            ],
        },
    }
}


async def assert_setup_sensor(hass, config, count=1):
    """Set up the sensor and assert it's been created."""
    with assert_setup_component(count):
        assert await async_setup_component(hass, sensor.DOMAIN, config)
        await hass.async_block_till_done()


@pytest.fixture
def mock_nextbus():
    """Create a mock py_nextbus module."""
    with patch(
        "homeassistant.components.nextbus.sensor.NextBusClient"
    ) as NextBusClient:
        yield NextBusClient


@pytest.fixture
def mock_nextbus_predictions(mock_nextbus):
    """Create a mock of NextBusClient predictions."""
    instance = mock_nextbus.return_value
    instance.get_predictions_for_multi_stops.return_value = BASIC_RESULTS

    yield instance.get_predictions_for_multi_stops


@pytest.fixture
def mock_nextbus_lists(mock_nextbus):
    """Mock all list functions in nextbus to test validate logic."""
    instance = mock_nextbus.return_value
    instance.get_agency_list.return_value = {
        "agency": [{"tag": "sf-muni", "title": "San Francisco Muni"}]
    }
    instance.get_route_list.return_value = {
        "route": [{"tag": "F", "title": "F - Market & Wharves"}]
    }
    instance.get_route_config.return_value = {
        "route": {"stop": [{"tag": "5650", "title": "Market St & 7th St"}]}
    }


async def test_valid_config(hass, mock_nextbus, mock_nextbus_lists):
    """Test that sensor is set up properly with valid config."""
    await assert_setup_sensor(hass, CONFIG_BASIC)


async def test_invalid_config(hass, mock_nextbus, mock_nextbus_lists):
    """Checks that component is not setup when missing information."""
    await assert_setup_sensor(hass, CONFIG_INVALID_MISSING, count=0)


async def test_validate_tags(hass, mock_nextbus, mock_nextbus_lists):
    """Test that additional validation against the API is successful."""
    # with self.subTest('Valid everything'):
    assert nextbus.validate_tags(mock_nextbus(), VALID_AGENCY, VALID_ROUTE, VALID_STOP)
    # with self.subTest('Invalid agency'):
    assert not nextbus.validate_tags(
        mock_nextbus(), "not-valid", VALID_ROUTE, VALID_STOP
    )

    # with self.subTest('Invalid route'):
    assert not nextbus.validate_tags(mock_nextbus(), VALID_AGENCY, "0", VALID_STOP)

    # with self.subTest('Invalid stop'):
    assert not nextbus.validate_tags(mock_nextbus(), VALID_AGENCY, VALID_ROUTE, 0)


async def test_verify_valid_state(
    hass, mock_nextbus, mock_nextbus_lists, mock_nextbus_predictions
):
    """Verify all attributes are set from a valid response."""
    await assert_setup_sensor(hass, CONFIG_BASIC)
    mock_nextbus_predictions.assert_called_once_with(
        [{"stop_tag": VALID_STOP, "route_tag": VALID_ROUTE}], VALID_AGENCY
    )

    state = hass.states.get(SENSOR_ID_SHORT)
    assert state is not None
    assert state.state == "2019-03-28T21:09:31+00:00"
    assert state.attributes["agency"] == VALID_AGENCY_TITLE
    assert state.attributes["route"] == VALID_ROUTE_TITLE
    assert state.attributes["stop"] == VALID_STOP_TITLE
    assert state.attributes["direction"] == "Outbound"
    assert state.attributes["upcoming"] == "1, 2, 3"


async def test_message_dict(
    hass, mock_nextbus, mock_nextbus_lists, mock_nextbus_predictions
):
    """Verify that a single dict message is rendered correctly."""
    mock_nextbus_predictions.return_value = {
        "predictions": {
            "agencyTitle": VALID_AGENCY_TITLE,
            "routeTitle": VALID_ROUTE_TITLE,
            "stopTitle": VALID_STOP_TITLE,
            "message": {"text": "Message"},
            "direction": {
                "title": "Outbound",
                "prediction": [
                    {"minutes": "1", "epochTime": "1553807371000"},
                    {"minutes": "2", "epochTime": "1553807372000"},
                    {"minutes": "3", "epochTime": "1553807373000"},
                ],
            },
        }
    }

    await assert_setup_sensor(hass, CONFIG_BASIC)

    state = hass.states.get(SENSOR_ID_SHORT)
    assert state is not None
    assert state.attributes["message"] == "Message"


async def test_message_list(
    hass, mock_nextbus, mock_nextbus_lists, mock_nextbus_predictions
):
    """Verify that a list of messages are rendered correctly."""
    mock_nextbus_predictions.return_value = {
        "predictions": {
            "agencyTitle": VALID_AGENCY_TITLE,
            "routeTitle": VALID_ROUTE_TITLE,
            "stopTitle": VALID_STOP_TITLE,
            "message": [{"text": "Message 1"}, {"text": "Message 2"}],
            "direction": {
                "title": "Outbound",
                "prediction": [
                    {"minutes": "1", "epochTime": "1553807371000"},
                    {"minutes": "2", "epochTime": "1553807372000"},
                    {"minutes": "3", "epochTime": "1553807373000"},
                ],
            },
        }
    }

    await assert_setup_sensor(hass, CONFIG_BASIC)

    state = hass.states.get(SENSOR_ID_SHORT)
    assert state is not None
    assert state.attributes["message"] == "Message 1 -- Message 2"


async def test_direction_list(
    hass, mock_nextbus, mock_nextbus_lists, mock_nextbus_predictions
):
    """Verify that a list of messages are rendered correctly."""
    mock_nextbus_predictions.return_value = {
        "predictions": {
            "agencyTitle": VALID_AGENCY_TITLE,
            "routeTitle": VALID_ROUTE_TITLE,
            "stopTitle": VALID_STOP_TITLE,
            "message": [{"text": "Message 1"}, {"text": "Message 2"}],
            "direction": [
                {
                    "title": "Outbound",
                    "prediction": [
                        {"minutes": "1", "epochTime": "1553807371000"},
                        {"minutes": "2", "epochTime": "1553807372000"},
                        {"minutes": "3", "epochTime": "1553807373000"},
                    ],
                },
                {
                    "title": "Outbound 2",
                    "prediction": {"minutes": "0", "epochTime": "1553807374000"},
                },
            ],
        }
    }

    await assert_setup_sensor(hass, CONFIG_BASIC)

    state = hass.states.get(SENSOR_ID_SHORT)
    assert state is not None
    assert state.state == "2019-03-28T21:09:31+00:00"
    assert state.attributes["agency"] == VALID_AGENCY_TITLE
    assert state.attributes["route"] == VALID_ROUTE_TITLE
    assert state.attributes["stop"] == VALID_STOP_TITLE
    assert state.attributes["direction"] == "Outbound, Outbound 2"
    assert state.attributes["upcoming"] == "0, 1, 2, 3"


async def test_custom_name(
    hass, mock_nextbus, mock_nextbus_lists, mock_nextbus_predictions
):
    """Verify that a custom name can be set via config."""
    config = deepcopy(CONFIG_BASIC)
    config["sensor"]["name"] = "Custom Name"

    await assert_setup_sensor(hass, config)
    state = hass.states.get("sensor.custom_name")
    assert state is not None


async def test_no_predictions(
    hass, mock_nextbus, mock_nextbus_predictions, mock_nextbus_lists
):
    """Verify there are no exceptions when no predictions are returned."""
    mock_nextbus_predictions.return_value = {}

    await assert_setup_sensor(hass, CONFIG_BASIC)

    state = hass.states.get(SENSOR_ID_SHORT)
    assert state is not None
    assert state.state == "unknown"


async def test_verify_no_upcoming(
    hass, mock_nextbus, mock_nextbus_lists, mock_nextbus_predictions
):
    """Verify attributes are set despite no upcoming times."""
    mock_nextbus_predictions.return_value = {
        "predictions": {
            "agencyTitle": VALID_AGENCY_TITLE,
            "routeTitle": VALID_ROUTE_TITLE,
            "stopTitle": VALID_STOP_TITLE,
            "direction": {"title": "Outbound", "prediction": []},
        }
    }

    await assert_setup_sensor(hass, CONFIG_BASIC)

    state = hass.states.get(SENSOR_ID_SHORT)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["upcoming"] == "No upcoming predictions"
