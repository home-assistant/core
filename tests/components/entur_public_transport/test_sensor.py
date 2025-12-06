"""Tests for the Entur public transport sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.entur_public_transport.const import (
    ATTR_DELAY,
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
    assert state.attributes.get("attribution") == "Data provided by Entur"


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
