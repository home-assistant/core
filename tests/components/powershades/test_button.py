"""Tests for the PowerShades button platform."""

import pytest

from homeassistant.components.powershades.const import (
    LIMIT_LOWER,
    LIMIT_UPPER,
    OP_CLEAR_LIMITS,
    OP_INDICATE,
    OP_JOG_DOWN,
    OP_JOG_UP,
    OP_SET_LIMIT,
    OP_SET_POSITION,
    OP_STEP_DOWN,
    OP_STEP_UP,
)
from homeassistant.components.powershades.protocol import (
    build_set_limit_payload,
    build_set_position_payload,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    ("key", "expected_call"),
    [
        ("identify", (OP_INDICATE, b"")),
        ("jog_up", (OP_JOG_UP, b"")),
        ("jog_down", (OP_JOG_DOWN, b"")),
        ("set_upper_limit", (OP_SET_LIMIT, build_set_limit_payload(LIMIT_UPPER))),
        ("set_lower_limit", (OP_SET_LIMIT, build_set_limit_payload(LIMIT_LOWER))),
        ("clear_limits", (OP_CLEAR_LIMITS, b"")),
        ("step_up", (OP_STEP_UP, b"")),
        ("step_down", (OP_STEP_DOWN, b"")),
    ],
)
async def test_button_press_sends_command(
    hass: HomeAssistant, config_entry, key: str, expected_call: tuple
) -> None:
    """Pressing a button sends the expected command to the device."""
    coordinator = config_entry.runtime_data
    entity_id = f"button.powershade_bedroom_shade_{key}"

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )

    coordinator.connection.async_request.assert_any_call(*expected_call)


async def test_toggle_button_toggles_shade(hass: HomeAssistant, config_entry) -> None:
    """Pressing the toggle button stops or moves the shade depending on state."""
    coordinator = config_entry.runtime_data
    entity_id = "button.powershade_bedroom_shade_toggle_shade"

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )

    # Position starts at 50 (the "mostly closed" boundary), so toggling opens it.
    coordinator.connection.async_request.assert_any_call(
        OP_SET_POSITION, build_set_position_payload(100)
    )


async def test_button_unique_ids(hass: HomeAssistant, config_entry) -> None:
    """All buttons get a unique id namespaced with the serial number."""
    registry = er.async_get(hass)
    entity_id = "button.powershade_bedroom_shade_jog_up"
    entry = registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == "powershades_12345_jog_up"
