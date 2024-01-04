"""Tests for lawn_mower module."""
import logging

import pytest

from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    ("activity", "state", "target_state"),
    [
        ("PARKED_IN_CS", "RESTRICTED", LawnMowerActivity.DOCKED),
        ("UNKNOWN", "PAUSED", LawnMowerActivity.PAUSED),
        ("MOWING", "NOT_APPLICABLE", LawnMowerActivity.MOWING),
        ("NOT_APPLICABLE", "ERROR", LawnMowerActivity.ERROR),
    ],
)
async def test_lawn_mower_states(
    hass: HomeAssistant, setup_entity, activity, state, target_state
) -> None:
    """Test lawn_mower state."""
    state = hass.states.get("lawn_mower.test_mower_1")
    assert state is not None
    assert state.state == target_state


async def test_lawn_mower_commands(
    hass: HomeAssistant, setup_entity, activity, state
) -> None:
    """Test lawn_mower commands."""

    await hass.services.async_call(
        domain="lawn_mower",
        service="start_mowing",
        service_data={"entity_id": "lawn_mower.test_mower_1"},
    )

    await hass.services.async_call(
        "lawn_mower",
        service="pause",
        service_data={"entity_id": "lawn_mower.test_mower_1"},
    )

    await hass.services.async_call(
        "lawn_mower",
        service="dock",
        service_data={"entity_id": "lawn_mower.test_mower_1"},
    )
