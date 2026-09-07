"""The tests for the nexbus sensor component."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import MagicMock
from urllib.error import HTTPError

from freezegun.api import FrozenDateTimeFactory
from py_nextbus.client import NextBusFormatError, NextBusHTTPError
import pytest

from homeassistant.components.nextbus import NEXTBUS_KEY
from homeassistant.components.nextbus.const import CONF_AGENCY, CONF_ROUTE, DOMAIN
from homeassistant.components.nextbus.coordinator import NextBusDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

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
    VALID_AGENCY_TITLE,
    VALID_ROUTE_TITLE,
    VALID_STOP_TITLE,
)

from tests.common import MockConfigEntry, async_fire_time_changed


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
    entry = await assert_setup_sensor(hass, CONFIG_BASIC)
    coordinator: NextBusDataUpdateCoordinator = entry.runtime_data
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


async def test_verify_throttle(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify that the sensor coordinator is throttled correctly."""

    # Set rate limit past threshold, should be ignored for first request
    mock_client = mock_nextbus.return_value
    mock_client.rate_limit_percent = 99.0
    mock_client.rate_limit_reset = dt_util.naive_now() + timedelta(seconds=30)

    # Do a request with the initial config and get predictions
    await assert_setup_sensor(hass, CONFIG_BASIC)

    # Validate the predictions are present
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2019-03-28T21:09:31+00:00"
    assert state.attributes["agency"] == VALID_AGENCY
    assert state.attributes["route"] == VALID_ROUTE_TITLE
    assert state.attributes["stop"] == VALID_STOP_TITLE
    assert state.attributes["upcoming"] == "1, 2, 3, 10"

    # Update the predictions mock to return a different result
    mock_nextbus_predictions.return_value = NO_UPCOMING

    # Move time forward and bump the rate limit reset time
    mock_client.rate_limit_reset = freezer.tick(31) + timedelta(seconds=30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify that the sensor state is unchanged
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2019-03-28T21:09:31+00:00"

    # Move time forward past the rate limit reset time
    freezer.tick(31)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify that the sensor state is updated with the new predictions
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.attributes["upcoming"] == "No upcoming predictions"
    assert state.state == "unknown"


async def test_concurrent_setup_shares_coordinator(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
) -> None:
    """Test that two entries set up concurrently share one coordinator."""
    entries = []
    for config, route_title in (
        (CONFIG_BASIC, VALID_ROUTE_TITLE),
        (CONFIG_BASIC_2, ROUTE_TITLE_2),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=config[DOMAIN],
            title=f"{VALID_AGENCY_TITLE} {route_title} {VALID_STOP_TITLE}",
            unique_id=(
                f"{config[DOMAIN][CONF_AGENCY]}"
                f"_{config[DOMAIN][CONF_ROUTE]}"
                f"_{config[DOMAIN][CONF_STOP]}"
            ),
        )
        entry.add_to_hass(hass)
        entries.append(entry)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[1].state is ConfigEntryState.LOADED
    assert entries[0].runtime_data is entries[1].runtime_data


async def test_unload_entry(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the sensor can be unloaded."""
    config_entry1 = await assert_setup_sensor(hass, CONFIG_BASIC)
    config_entry2 = await assert_setup_sensor(
        hass, CONFIG_BASIC_2, route_title=ROUTE_TITLE_2
    )

    assert config_entry1.runtime_data is config_entry2.runtime_data

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


async def test_unload_final_entry_cleans_up_shared_coordinator(
    hass: HomeAssistant,
    mock_nextbus: MagicMock,
    mock_nextbus_lists: MagicMock,
    mock_nextbus_predictions: MagicMock,
) -> None:
    """Test that unloading the final entry shuts down the shared coordinator."""
    config_entry1 = await assert_setup_sensor(hass, CONFIG_BASIC)
    config_entry2 = await assert_setup_sensor(
        hass, CONFIG_BASIC_2, route_title=ROUTE_TITLE_2
    )
    coordinator: NextBusDataUpdateCoordinator = config_entry1.runtime_data

    await hass.config_entries.async_unload(config_entry1.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry2.entry_id)
    await hass.async_block_till_done()

    assert config_entry1.state is ConfigEntryState.NOT_LOADED
    assert config_entry2.state is ConfigEntryState.NOT_LOADED
    assert coordinator._shutdown_requested
    assert hass.data[NEXTBUS_KEY] == {}
