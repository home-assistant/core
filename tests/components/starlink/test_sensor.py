"""Tests for the Starlink sensors."""

from copy import deepcopy

import pytest

from homeassistant.const import PERCENTAGE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import setup_integration
from .patchers import STATUS_DATA_FIXTURE

ENTITY_ID = "sensor.starlink_signal_quality"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("signal_quality", "expected_state"),
    [
        pytest.param(0.7, "70.0", id="reported"),
        pytest.param(0.0, "0.0", id="zero"),
        pytest.param(None, STATE_UNKNOWN, id="not_reported"),
    ],
)
async def test_signal_quality(
    hass: HomeAssistant, signal_quality: float | None, expected_state: str
) -> None:
    """Test the signal quality sensor."""
    status_data = deepcopy(STATUS_DATA_FIXTURE)
    status_data[0]["signal_quality"] = signal_quality

    await setup_integration(hass, status_data)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
