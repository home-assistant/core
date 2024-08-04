"""The tests for the nexbus sensor component."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from py_nextbus.client import NextBusFormatError, NextBusHTTPError
import pytest

from homeassistant.components import sensor
from homeassistant.components.nextbus.const import CONF_AGENCY, CONF_ROUTE, DOMAIN
from homeassistant.components.nextbus.coordinator import NextBusDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

VALID_AGENCY = "sfmta-cis"
VALID_ROUTE = "F"
VALID_STOP = "5184"
VALID_AGENCY_TITLE = "San Francisco Muni"
VALID_ROUTE_TITLE = "F-Market & Wharves"
VALID_STOP_TITLE = "Market St & 7th St"
SENSOR_ID = "sensor.san_francisco_muni_f_market_wharves_market_st_7th_st"

PLATFORM_CONFIG = {
    sensor.DOMAIN: {
        "platform": DOMAIN,
        CONF_AGENCY: VALID_AGENCY,
        CONF_ROUTE: VALID_ROUTE,
        CONF_STOP: VALID_STOP,
    },
}


CONFIG_BASIC = {
    DOMAIN: {
        CONF_AGENCY: VALID_AGENCY,
        CONF_ROUTE: VALID_ROUTE,
        CONF_STOP: VALID_STOP,
    }
}

BASIC_RESULTS = [
    {
        "route": {
            "title": VALID_ROUTE_TITLE,
            "id": VALID_ROUTE,
        },
        "stop": {
            "name": VALID_STOP_TITLE,
            "id": VALID_STOP,
        },
        "values": [
            {"minutes": 1, "timestamp": 1553807371000},
            {"minutes": 2, "timestamp": 1553807372000},
            {"minutes": 3, "timestamp": 1553807373000},
            {"minutes": 10, "timestamp": 1553807380000},
        ],
    }
]

NO_UPCOMING = [
    {
        "route": {
            "title": VALID_ROUTE_TITLE,
            "id": VALID_ROUTE,
        },
        "stop": {
            "name": VALID_STOP_TITLE,
            "id": VALID_STOP,
        },
        "values": [],
    }
]


@pytest.fixture
def mock_nextbus() -> Generator[MagicMock]:
    """Create a mock py_nextbus module."""
    with patch("homeassistant.components.nextbus.coordinator.NextBusClient") as client:
        yield client


@pytest.fixture
def mock_nextbus_predictions(
    mock_nextbus: MagicMock,
) -> Generator[MagicMock]:
    """Create a mock of NextBusClient predictions."""
    instance = mock_nextbus.return_value
    instance.predictions_for_stop.return_value = BASIC_RESULTS

    return instance.predictions_for_stop


async def assert_setup_sensor(
    hass: HomeAssistant,
    config: dict[str, dict[str, str]],
    expected_state=ConfigEntryState.LOADED,
) -> MockConfigEntry:
    """Set up the sensor and assert it's been created."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config[DOMAIN],
        title=f"{VALID_AGENCY_TITLE} {VALID_ROUTE_TITLE} {VALID_STOP_TITLE}",
        unique_id=f"{VALID_AGENCY}_{VALID_ROUTE}_{VALID_STOP}",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is expected_state

    return config_entry


async def test_predictions(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
) -> None:
    """Verify that a list of messages are rendered correctly."""

    await assert_setup_sensor(hass, CONFIG_BASIC)

    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2019-03-28T21:09:31+00:00"
    assert state.attributes["agency"] == VALID_AGENCY
    assert state.attributes["route"] == VALID_ROUTE_TITLE
    assert state.attributes["stop"] == VALID_STOP_TITLE
    assert state.attributes["upcoming"] == "1, 2, 3, 10"


@pytest.mark.parametrize(
    "client_exception",
    [
        NextBusHTTPError("failed", HTTPError("url", 500, "error", MagicMock(), None)),
        NextBusFormatError("failed"),
    ],
)
async def test_prediction_exceptions(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
    client_exception: Exception,
) -> None:
    """Test that some coodinator exceptions raise UpdateFailed exceptions."""
    await assert_setup_sensor(hass, CONFIG_BASIC)
    coordinator: NextBusDataUpdateCoordinator = hass.data[DOMAIN][VALID_AGENCY]
    mock_nextbus_predictions.side_effect = client_exception
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_custom_name(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
) -> None:
    """Verify that a custom name can be set via config."""
    config = deepcopy(CONFIG_BASIC)
    config[DOMAIN][CONF_NAME] = "Custom Name"

    await assert_setup_sensor(hass, config)
    state = hass.states.get("sensor.custom_name")
    assert state is not None
    assert state.name == "Custom Name"


async def test_verify_no_predictions(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
) -> None:
    """Verify attributes are set despite no upcoming times."""
    mock_nextbus_predictions.return_value = []
    await assert_setup_sensor(hass, CONFIG_BASIC)

    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert "upcoming" not in state.attributes
    assert state.state == "unknown"


async def test_verify_no_upcoming(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
) -> None:
    """Verify attributes are set despite no upcoming times."""
    mock_nextbus_predictions.return_value = NO_UPCOMING
    await assert_setup_sensor(hass, CONFIG_BASIC)

    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.attributes["upcoming"] == "No upcoming predictions"
    assert state.state == "unknown"
