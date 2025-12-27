"""Tests for the Entur public transport sensor platform."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from homeassistant.components.entur_public_transport.const import (
    ATTR_DELAY,
    ATTR_EXPECTED_AT,
    ATTR_NEXT_UP_AT,
    ATTR_NEXT_UP_DELAY,
    ATTR_NEXT_UP_IN,
    ATTR_NEXT_UP_REALTIME,
    ATTR_NEXT_UP_ROUTE,
    ATTR_NEXT_UP_ROUTE_ID,
    ATTR_REALTIME,
    ATTR_ROUTE,
    ATTR_ROUTE_ID,
    ATTR_STOP_ID,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_sensor_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_place: MagicMock,
) -> None:
    """Test sensor state."""
    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None
    assert state.attributes.get("unit_of_measurement") == UnitOfTime.MINUTES
    assert (
        state.attributes.get("attribution") == "Data provided by entur.org under NLOD"
    )


@pytest.mark.usefixtures("init_integration")
async def test_sensor_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_estimated_call: MagicMock,
) -> None:
    """Test sensor attributes."""
    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None

    assert state.attributes.get(ATTR_STOP_ID) == "NSR:StopPlace:548"
    assert state.attributes.get(ATTR_ROUTE) == mock_estimated_call.front_display
    assert state.attributes.get(ATTR_ROUTE_ID) == mock_estimated_call.line_id
    assert state.attributes.get(ATTR_REALTIME) == mock_estimated_call.is_realtime
    assert state.attributes.get(ATTR_DELAY) == mock_estimated_call.delay_in_min


@pytest.mark.usefixtures("init_integration")
async def test_sensor_icon(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor icon."""
    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None
    assert state.attributes.get("icon") == "mdi:train"


async def test_sensor_unavailable_when_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
) -> None:
    """Test sensor is unavailable when no data."""
    mock_entur_client.get_stop_info.return_value = None
    mock_entur_client.all_stop_places_quays.return_value = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.entur_bergen_stasjon")
    # No entities should be created if no stops are returned
    assert state is None


async def test_sensor_with_multiple_departures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
    mock_place: MagicMock,
) -> None:
    """Test sensor with multiple departures shows next departure info."""
    # Create multiple estimated calls
    first_call = MagicMock()
    first_call.is_realtime = True
    first_call.expected_departure_time = datetime.now(tz=UTC) + timedelta(minutes=5)
    first_call.front_display = "45 Voss"
    first_call.line_id = "NSB:Line:45"
    first_call.transport_mode = "rail"
    first_call.delay_in_min = 0

    second_call = MagicMock()
    second_call.is_realtime = False
    second_call.expected_departure_time = datetime.now(tz=UTC) + timedelta(minutes=15)
    second_call.front_display = "60 Oslo"
    second_call.line_id = "NSB:Line:60"
    second_call.transport_mode = "rail"
    second_call.delay_in_min = 2

    mock_place.estimated_calls = [first_call, second_call]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None

    # First departure
    assert state.attributes.get(ATTR_ROUTE) == "45 Voss"
    assert state.attributes.get(ATTR_EXPECTED_AT) is not None

    # Next departure
    assert state.attributes.get(ATTR_NEXT_UP_ROUTE) == "60 Oslo"
    assert state.attributes.get(ATTR_NEXT_UP_ROUTE_ID) == "NSB:Line:60"
    assert state.attributes.get(ATTR_NEXT_UP_AT) is not None
    assert state.attributes.get(ATTR_NEXT_UP_IN) is not None
    assert state.attributes.get(ATTR_NEXT_UP_REALTIME) is False
    assert state.attributes.get(ATTR_NEXT_UP_DELAY) == 2


async def test_sensor_no_estimated_calls(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
    mock_place: MagicMock,
) -> None:
    """Test sensor when there are no estimated calls."""
    mock_place.estimated_calls = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None
    # State should be None/unknown when no departures
    assert state.state == "unknown"
    # Icon should be default (bus) when no calls
    assert state.attributes.get("icon") == "mdi:bus"


async def test_sensor_with_three_or_more_departures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
    mock_place: MagicMock,
) -> None:
    """Test sensor with 3+ departures shows additional departure info."""
    # Create multiple estimated calls
    first_call = MagicMock()
    first_call.is_realtime = True
    first_call.expected_departure_time = datetime.now(tz=UTC) + timedelta(minutes=5)
    first_call.front_display = "45 Voss"
    first_call.line_id = "NSB:Line:45"
    first_call.transport_mode = "rail"
    first_call.delay_in_min = 0

    second_call = MagicMock()
    second_call.is_realtime = True
    second_call.expected_departure_time = datetime.now(tz=UTC) + timedelta(minutes=15)
    second_call.front_display = "60 Oslo"
    second_call.line_id = "NSB:Line:60"
    second_call.transport_mode = "rail"
    second_call.delay_in_min = 0

    third_call = MagicMock()
    third_call.is_realtime = True
    third_call.expected_departure_time = datetime.now(tz=UTC) + timedelta(minutes=25)
    third_call.front_display = "70 Trondheim"
    third_call.line_id = "NSB:Line:70"
    third_call.transport_mode = "rail"
    third_call.delay_in_min = 0

    fourth_call = MagicMock()
    fourth_call.is_realtime = False  # Not realtime - should have "ca. " prefix
    fourth_call.expected_departure_time = datetime.now(tz=UTC) + timedelta(minutes=35)
    fourth_call.front_display = "80 Stavanger"
    fourth_call.line_id = "NSB:Line:80"
    fourth_call.transport_mode = "rail"
    fourth_call.delay_in_min = 0

    mock_place.estimated_calls = [first_call, second_call, third_call, fourth_call]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None

    # Check additional departures are present
    departure_3 = state.attributes.get("departure_#3")
    assert departure_3 is not None
    assert "70 Trondheim" in departure_3
    assert not departure_3.startswith("ca.")  # realtime, no prefix

    departure_4 = state.attributes.get("departure_#4")
    assert departure_4 is not None
    assert "80 Stavanger" in departure_4
    assert departure_4.startswith("ca.")  # not realtime, has prefix
