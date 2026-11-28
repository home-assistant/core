"""Tests for the Starlink sensors."""

from copy import deepcopy

import pytest

from homeassistant.const import PERCENTAGE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from . import STATUS_DATA_FIXTURE

ENTITY_ID = "sensor.starlink_signal_quality"


def _status_with_signal_quality(signal_quality: float | None) -> JsonArrayType:
    """Return status data with the given signal quality."""
    status_data = deepcopy(STATUS_DATA_FIXTURE)
    status_data[0]["signal_quality"] = signal_quality
    return status_data


@pytest.mark.parametrize(
    ("status_data", "expected_state"),
    [
        pytest.param(_status_with_signal_quality(0.7), "70.0", id="reported"),
        pytest.param(_status_with_signal_quality(0.0), "0.0", id="zero"),
        pytest.param(
            _status_with_signal_quality(None), STATE_UNKNOWN, id="not_reported"
        ),
    ],
    indirect=["status_data"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_signal_quality(hass: HomeAssistant, expected_state: str) -> None:
    """Test the signal quality sensor."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
