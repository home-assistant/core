"""The tests for the nexbus sensor component."""

from copy import deepcopy
from unittest.mock import MagicMock
from urllib.error import HTTPError

from freezegun.api import FrozenDateTimeFactory
from py_nextbus.client import NextBusFormatError, NextBusHTTPError
import pytest

from homeassistant.components.nextbus.const import DOMAIN
from homeassistant.components.nextbus.coordinator import NextBusDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import assert_setup_sensor
from .const import (
    BASIC_RESULTS,
    CONFIG_BASIC,
    CONFIG_BASIC_2,
    NO_UPCOMING,
    ROUTE_TITLE_2,
    SENSOR_ID,
    SENSOR_ID_2,
    VALID_AGENCY,
    VALID_COORDINATOR_KEY,
    VALID_ROUTE_TITLE,
    VALID_STOP_TITLE,
)

from tests.common import async_fire_time_changed


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
    coordinator: NextBusDataUpdateCoordinator = hass.data[DOMAIN][VALID_COORDINATOR_KEY]
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


async def test_unload_entry(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the sensor can be unloaded."""
    config_entry1 = await assert_setup_sensor(hass, CONFIG_BASIC)
    await assert_setup_sensor(hass, CONFIG_BASIC_2, route_title=ROUTE_TITLE_2)

    # Verify the first sensor
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2019-03-28T21:09:31+00:00"
    assert state.attributes["agency"] == VALID_AGENCY
    assert state.attributes["route"] == VALID_ROUTE_TITLE
    assert state.attributes["stop"] == VALID_STOP_TITLE
    assert state.attributes["upcoming"] == "1, 2, 3, 10"

    # Verify the second sensor
    state = hass.states.get(SENSOR_ID_2)
    assert state is not None
    assert state.state == "2019-03-28T21:09:39+00:00"
    assert state.attributes["agency"] == VALID_AGENCY
    assert state.attributes["route"] == ROUTE_TITLE_2
    assert state.attributes["stop"] == VALID_STOP_TITLE
    assert state.attributes["upcoming"] == "90"

    # Update mock to return new predictions
    new_predictions = deepcopy(BASIC_RESULTS)
    new_predictions[1]["values"] = [{"minutes": 5, "timestamp": 1553807375000}]
    mock_nextbus_predictions.return_value = new_predictions

    # Unload config entry 1
    await hass.config_entries.async_unload(config_entry1.entry_id)
    await hass.async_block_till_done()
    assert config_entry1.state is ConfigEntryState.NOT_LOADED

    # Skip ahead in time
    freezer.tick(120)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Check update for new predictions
    state = hass.states.get(SENSOR_ID_2)
    assert state is not None
    assert state.attributes["upcoming"] == "5"
    assert state.state == "2019-03-28T21:09:35+00:00"
