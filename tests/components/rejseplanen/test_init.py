"""Test the Rejseplanen integration setup and coordinator behavior."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from py_rejseplan.enums import TransportClass
from py_rejseplan.exceptions.api_error import APIError
from py_rejseplan.exceptions.connection_error import ConnectionError
from py_rejseplan.exceptions.http_error import HTTPError
import pytest

from homeassistant.components.rejseplanen.const import (
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY, CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_ENTITY_ID = "sensor.work_line"


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
@pytest.mark.usefixtures("setup_integration")
async def test_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the integration sets up and entities become available."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(TEST_ENTITY_ID)
    assert state is not None
    assert state.state == "Bus 207"


@pytest.mark.parametrize(
    "error",
    [
        APIError("api error"),
        HTTPError("http error", status_code=500),
        ConnectionError("connection error"),
        TypeError("type error"),
    ],
)
async def test_setup_first_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    error: Exception,
) -> None:
    """Test that a failing first refresh results in a setup retry."""
    mock_api.get_departures_async.side_effect = error

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_first_refresh_auth_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test that an auth error during first refresh puts the entry in an error state."""
    mock_api.get_departures_async.side_effect = HTTPError(
        "unauthorized", status_code=401
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
@pytest.mark.parametrize(
    "error",
    [
        APIError("api error"),
        HTTPError("http error", status_code=500),
        ConnectionError("connection error"),
        TypeError("type error"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_update_failure_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """Test that a failed refresh marks entities unavailable."""
    assert hass.states.get(TEST_ENTITY_ID).state == "Bus 207"

    mock_api.get_departures_async.side_effect = error
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
@pytest.mark.usefixtures("setup_integration")
async def test_update_auth_failure_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an auth error during a refresh marks entities unavailable."""
    assert hass.states.get(TEST_ENTITY_ID).state == "Bus 207"

    mock_api.get_departures_async.side_effect = HTTPError(
        "unauthorized", status_code=401
    )
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
async def test_setup_without_stops(
    hass: HomeAssistant,
    mock_api: AsyncMock,
) -> None:
    """Test that an entry with no stop subentries loads without entities."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert not hass.states.async_entity_ids("sensor")
    mock_api.get_departures_async.assert_not_called()


@pytest.mark.freeze_time("2024-01-01 11:00:00+00:00")
async def test_departure_type_filter(
    hass: HomeAssistant,
    mock_api: AsyncMock,
) -> None:
    """Test that departures are filtered by the configured departure type.

    Stop 456789 has BUS, TOG and ICL departures. Filtering on ICL leaves
    only the future ICL departure.
    """
    mock_api.calculate_departure_type_bitflag.return_value = int(TransportClass.ICL)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_STOP_ID: 456789,
                    CONF_NAME: "Gym",
                    CONF_DIRECTION: [],
                    CONF_DEPARTURE_TYPE: [TransportClass.ICL],
                },
                subentry_type="stop",
                title="Gym",
                subentry_id="gym-subentry-id",
                unique_id=None,
            ),
        ],
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.gym_number_of_departures").state == "1"
    assert (
        hass.states.get("sensor.gym_departing_in").state == "2024-01-01T11:12:00+00:00"
    )
