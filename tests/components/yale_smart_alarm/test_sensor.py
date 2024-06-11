"""The test for the sensibo sensor."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_setup_and_update_errors(
    hass: HomeAssistant,
    load_config_entry: tuple[MockConfigEntry, Mock],
    load_json: dict[str, Any],
) -> None:
    """Test the Yale Smart Living coordinator with errors."""

    state = hass.states.get("sensor.smoke_alarm_temperature")
    assert state.state == "21"
