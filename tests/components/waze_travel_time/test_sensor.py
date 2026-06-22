"""Test Waze Travel Time sensors."""

import httpx
import pytest
from pywaze.route_calculator import WRCError

from homeassistant.components.waze_travel_time.config_flow import WazeConfigFlow
from homeassistant.components.waze_travel_time.const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_REALTIME,
    CONF_TIME_DELTA,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_OPTIONS,
    DOMAIN,
    IMPERIAL_UNITS,
    METRIC_UNITS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry

ENTITY_ID = "sensor.waze_travel_time"


@pytest.fixture(name="mock_update_wrcerror")
def mock_update_wrcerror_fixture(mock_update):
    """Mock an update to the sensor failed with WRCError."""
    mock_update.side_effect = WRCError("test")
    return mock_update


@pytest.fixture(name="mock_update_connect_error")
def mock_update_connect_error_fixture(mock_update):
    """Mock an update to the sensor failed with httpx.ConnectError."""
    mock_update.side_effect = httpx.ConnectError("[Errno -3] Try again")
    return mock_update


@pytest.mark.parametrize(
    ("data", "options"),
    [(MOCK_CONFIG, DEFAULT_OPTIONS)],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_sensor(hass: HomeAssistant) -> None:
    """Test that sensor works."""

    assert (state := hass.states.get(ENTITY_ID))

    assert state.state == "150"
    assert state.attributes["attribution"] == "Powered by Waze"
    assert state.attributes["duration"] == 150
    assert state.attributes["distance"] == 300
    assert state.attributes["route"] == "E1337 - Teststreet"
    assert state.attributes["origin"] == "location1"
    assert state.attributes["destination"] == "location2"
    assert state.attributes["unit_of_measurement"] == "min"


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_UNITS: IMPERIAL_UNITS,
                CONF_REALTIME: True,
                CONF_VEHICLE_TYPE: "car",
                CONF_AVOID_TOLL_ROADS: True,
                CONF_AVOID_SUBSCRIPTION_ROADS: True,
                CONF_AVOID_FERRIES: True,
                CONF_INCL_FILTER: [""],
                CONF_EXCL_FILTER: [""],
                CONF_TIME_DELTA: {"minutes": 0},
            },
        )
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_imperial(hass: HomeAssistant) -> None:
    """Test that the imperial option works."""

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes["distance"] == pytest.approx(186.4113)


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_UNITS: METRIC_UNITS,
                CONF_REALTIME: True,
                CONF_VEHICLE_TYPE: "car",
                CONF_AVOID_TOLL_ROADS: True,
                CONF_AVOID_SUBSCRIPTION_ROADS: True,
                CONF_AVOID_FERRIES: True,
                CONF_INCL_FILTER: ["IncludeThis"],
                CONF_EXCL_FILTER: [""],
                CONF_TIME_DELTA: {"minutes": 0},
            },
        )
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_incl_filter(hass: HomeAssistant) -> None:
    """Test that incl_filter only includes route with the wanted street name."""

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes["distance"] == 300


@pytest.mark.parametrize(
    ("data", "options"),
    [
        (
            MOCK_CONFIG,
            {
                CONF_UNITS: METRIC_UNITS,
                CONF_REALTIME: True,
                CONF_VEHICLE_TYPE: "car",
                CONF_AVOID_TOLL_ROADS: True,
                CONF_AVOID_SUBSCRIPTION_ROADS: True,
                CONF_AVOID_FERRIES: True,
                CONF_INCL_FILTER: [""],
                CONF_EXCL_FILTER: ["ExcludeThis"],
                CONF_TIME_DELTA: {"minutes": 0},
            },
        )
    ],
)
@pytest.mark.usefixtures("mock_update", "mock_config")
async def test_excl_filter(hass: HomeAssistant) -> None:
    """Test that excl_filter only includes route without the street name."""

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes["distance"] == 300


@pytest.mark.parametrize(
    ("error_fixture", "log_message"),
    [
        pytest.param(
            "mock_update_wrcerror", "Error on retrieving data: ", id="wrcerror"
        ),
        pytest.param(
            "mock_update_connect_error", "Connection error: ", id="connect_error"
        ),
    ],
)
async def test_sensor_failed(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    error_fixture: str,
    log_message: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test that sensor update fails with log message."""
    request.getfixturevalue(error_fixture)
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        options=DEFAULT_OPTIONS,
        entry_id="test",
        version=WazeConfigFlow.VERSION,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert log_message in caplog.text
