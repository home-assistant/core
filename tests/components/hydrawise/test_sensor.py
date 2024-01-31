"""Test Hydrawise sensor."""

from collections.abc import Awaitable, Callable

from freezegun.api import FrozenDateTimeFactory
from pydrawise.schema import Zone
import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.freeze_time("2023-10-01 00:00:00+00:00")
async def test_states(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor states."""
    watering_time1 = hass.states.get("sensor.zone_one_watering_time")
    assert watering_time1 is not None
    assert watering_time1.state == "0"

    watering_time2 = hass.states.get("sensor.zone_two_watering_time")
    assert watering_time2 is not None
    assert watering_time2.state == "29"

    next_cycle = hass.states.get("sensor.zone_one_next_cycle")
    assert next_cycle is not None
    assert next_cycle.state == "2023-10-04T19:49:57+00:00"


@pytest.mark.freeze_time("2023-10-01 00:00:00+00:00")
async def test_suspended_state(
    hass: HomeAssistant,
    zones: list[Zone],
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
) -> None:
    """Test sensor states."""
    zones[0].scheduled_runs.next_run = None
    await mock_add_config_entry()

    next_cycle = hass.states.get("sensor.zone_one_next_cycle")
    assert next_cycle is not None
    assert next_cycle.state == "9999-12-31T23:59:59+00:00"
