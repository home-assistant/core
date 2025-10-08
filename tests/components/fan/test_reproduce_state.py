"""Test reproduce state for Fan."""

import pytest

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reproducing Fan states."""
    hass.states.async_set("fan.entity_off", "off", {})
    hass.states.async_set("fan.entity_on", "on", {})
    hass.states.async_set("fan.entity_speed", "on", {"percentage": 100})
    hass.states.async_set("fan.entity_oscillating", "on", {"oscillating": True})
    hass.states.async_set("fan.entity_direction", "on", {"direction": "forward"})

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_calls = async_mock_service(hass, "fan", "set_percentage")

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("fan.entity_off", "off"),
            State("fan.entity_on", "on"),
            State("fan.entity_speed", "on", {"percentage": 100}),
            State("fan.entity_oscillating", "on", {"oscillating": True}),
            State("fan.entity_direction", "on", {"direction": "forward"}),
        ],
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(hass, [State("fan.entity_off", "not_supported")])

    assert "not_supported" in caplog.text
    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0
    assert len(set_percentage_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State("fan.entity_on", "off"),
            State("fan.entity_off", "on"),
            State("fan.entity_speed", "on", {"percentage": 25}),
            State("fan.entity_oscillating", "on", {"oscillating": False}),
            State("fan.entity_direction", "on", {"direction": "reverse"}),
            # Should not raise
            State("fan.non_existing", "on"),
        ],
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "fan"
    assert turn_on_calls[0].data == {"entity_id": "fan.entity_off"}

    assert len(set_direction_calls) == 1
    assert set_direction_calls[0].domain == "fan"
    assert set_direction_calls[0].data == {
        "entity_id": "fan.entity_direction",
        "direction": "reverse",
    }

    assert len(oscillate_calls) == 1
    assert oscillate_calls[0].domain == "fan"
    assert oscillate_calls[0].data == {
        "entity_id": "fan.entity_oscillating",
        "oscillating": False,
    }

    assert len(set_percentage_calls) == 1
    assert set_percentage_calls[0].domain == "fan"
    assert set_percentage_calls[0].data == {
        "entity_id": "fan.entity_speed",
        "percentage": 25,
    }

    assert len(turn_off_calls) == 1
    assert turn_off_calls[0].domain == "fan"
    assert turn_off_calls[0].data == {"entity_id": "fan.entity_on"}


MODERN_FAN_ENTITY = "fan.modern_fan"
MODERN_FAN_OFF_PERCENTAGE10_STATE = {
    ATTR_OSCILLATING: True,
    ATTR_DIRECTION: DIRECTION_FORWARD,
    ATTR_PERCENTAGE: 10,
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}
MODERN_FAN_OFF_PERCENTAGE15_STATE = {
    ATTR_OSCILLATING: True,
    ATTR_DIRECTION: DIRECTION_FORWARD,
    ATTR_PERCENTAGE: 15,
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}
MODERN_FAN_ON_INVALID_STATE = {
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}
MODERN_FAN_OFF_PPRESET_MODE_AUTO_STATE = {
    ATTR_OSCILLATING: True,
    ATTR_DIRECTION: DIRECTION_FORWARD,
    ATTR_PRESET_MODE: "Auto",
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}
MODERN_FAN_OFF_PPRESET_MODE_ECO_STATE = {
    ATTR_OSCILLATING: True,
    ATTR_DIRECTION: DIRECTION_FORWARD,
    ATTR_PRESET_MODE: "Eco",
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}
MODERN_FAN_ON_PERCENTAGE10_STATE = {
    ATTR_OSCILLATING: True,
    ATTR_DIRECTION: DIRECTION_FORWARD,
    ATTR_PERCENTAGE: 10,
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}
MODERN_FAN_ON_PERCENTAGE15_STATE = {
    ATTR_OSCILLATING: True,
    ATTR_DIRECTION: DIRECTION_FORWARD,
    ATTR_PERCENTAGE: 15,
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}
MODERN_FAN_ON_PRESET_MODE_AUTO_STATE = {
    ATTR_OSCILLATING: True,
    ATTR_DIRECTION: DIRECTION_FORWARD,
    ATTR_PRESET_MODE: "Auto",
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}
MODERN_FAN_ON_PRESET_MODE_ECO_STATE = {
    ATTR_OSCILLATING: True,
    ATTR_DIRECTION: DIRECTION_FORWARD,
    ATTR_PRESET_MODE: "Eco",
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}
MODERN_FAN_PRESET_MODE_AUTO_REVERSE_STATE = {
    ATTR_OSCILLATING: True,
    ATTR_DIRECTION: DIRECTION_REVERSE,
    ATTR_PRESET_MODE: "Auto",
    ATTR_PRESET_MODES: ["Auto", "Eco"],
}


@pytest.mark.parametrize(
    "start_state",
    [
        MODERN_FAN_OFF_PERCENTAGE10_STATE,
        MODERN_FAN_OFF_PERCENTAGE15_STATE,
        MODERN_FAN_OFF_PPRESET_MODE_AUTO_STATE,
        MODERN_FAN_OFF_PPRESET_MODE_ECO_STATE,
    ],
)
async def test_modern_turn_on_invalid(hass: HomeAssistant, start_state) -> None:
    """Test modern fan state reproduction, turning on with invalid state."""
    hass.states.async_set(MODERN_FAN_ENTITY, "off", start_state)

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_mode = async_mock_service(hass, "fan", "set_percentage")
    set_preset_mode = async_mock_service(hass, "fan", "set_preset_mode")

    # Turn on with an invalid config (speed, percentage, preset_modes all None)
    await async_reproduce_state(
        hass, [State(MODERN_FAN_ENTITY, "on", MODERN_FAN_ON_INVALID_STATE)]
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "fan"
    assert turn_on_calls[0].data == {"entity_id": MODERN_FAN_ENTITY}

    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 1
    assert set_direction_calls[0].domain == "fan"
    assert set_direction_calls[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_DIRECTION: None,
    }
    assert len(oscillate_calls) == 1
    assert oscillate_calls[0].domain == "fan"
    assert oscillate_calls[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_OSCILLATING: None,
    }
    assert len(set_percentage_mode) == 0
    assert len(set_preset_mode) == 0


@pytest.mark.parametrize(
    "start_state",
    [
        MODERN_FAN_OFF_PERCENTAGE10_STATE,
        MODERN_FAN_OFF_PPRESET_MODE_AUTO_STATE,
        MODERN_FAN_OFF_PPRESET_MODE_ECO_STATE,
    ],
)
async def test_modern_turn_on_percentage_from_different_speed(
    hass: HomeAssistant, start_state
) -> None:
    """Test modern fan state reproduction, turning on with a different percentage of the state."""
    hass.states.async_set(MODERN_FAN_ENTITY, "off", start_state)

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_mode = async_mock_service(hass, "fan", "set_percentage")
    set_preset_mode = async_mock_service(hass, "fan", "set_preset_mode")

    await async_reproduce_state(
        hass, [State(MODERN_FAN_ENTITY, "on", MODERN_FAN_ON_PERCENTAGE15_STATE)]
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "fan"
    assert turn_on_calls[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_PERCENTAGE: 15,
    }

    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0
    assert len(set_percentage_mode) == 0
    assert len(set_preset_mode) == 0


async def test_modern_turn_on_percentage_from_same_speed(hass: HomeAssistant) -> None:
    """Test modern fan state reproduction, turning on with the same percentage as in the state."""
    hass.states.async_set(MODERN_FAN_ENTITY, "off", MODERN_FAN_OFF_PERCENTAGE15_STATE)

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_mode = async_mock_service(hass, "fan", "set_percentage")
    set_preset_mode = async_mock_service(hass, "fan", "set_preset_mode")

    await async_reproduce_state(
        hass, [State(MODERN_FAN_ENTITY, "on", MODERN_FAN_ON_PERCENTAGE15_STATE)]
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "fan"
    assert turn_on_calls[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_PERCENTAGE: 15,
    }

    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0
    assert len(set_percentage_mode) == 0
    assert len(set_preset_mode) == 0


@pytest.mark.parametrize(
    "start_state",
    [
        MODERN_FAN_OFF_PERCENTAGE10_STATE,
        MODERN_FAN_OFF_PERCENTAGE15_STATE,
        MODERN_FAN_OFF_PPRESET_MODE_ECO_STATE,
    ],
)
async def test_modern_turn_on_preset_mode_from_different_speed(
    hass: HomeAssistant, start_state
) -> None:
    """Test modern fan state reproduction, turning on with a different preset mode from the state."""
    hass.states.async_set(MODERN_FAN_ENTITY, "off", start_state)

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_mode = async_mock_service(hass, "fan", "set_percentage")
    set_preset_mode = async_mock_service(hass, "fan", "set_preset_mode")

    await async_reproduce_state(
        hass, [State(MODERN_FAN_ENTITY, "on", MODERN_FAN_ON_PRESET_MODE_AUTO_STATE)]
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "fan"
    assert turn_on_calls[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_PRESET_MODE: "Auto",
    }

    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0
    assert len(set_percentage_mode) == 0
    assert len(set_preset_mode) == 0


async def test_modern_turn_on_preset_mode_from_same_speed(hass: HomeAssistant) -> None:
    """Test modern fan state reproduction, turning on with the same preset mode as in the state."""
    hass.states.async_set(
        MODERN_FAN_ENTITY, "off", MODERN_FAN_OFF_PPRESET_MODE_AUTO_STATE
    )

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_mode = async_mock_service(hass, "fan", "set_percentage")
    set_preset_mode = async_mock_service(hass, "fan", "set_preset_mode")

    await async_reproduce_state(
        hass, [State(MODERN_FAN_ENTITY, "on", MODERN_FAN_ON_PRESET_MODE_AUTO_STATE)]
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "fan"
    assert turn_on_calls[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_PRESET_MODE: "Auto",
    }

    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0
    assert len(set_percentage_mode) == 0
    assert len(set_preset_mode) == 0


@pytest.mark.parametrize(
    "start_state",
    [
        MODERN_FAN_OFF_PERCENTAGE10_STATE,
        MODERN_FAN_OFF_PERCENTAGE15_STATE,
        MODERN_FAN_OFF_PPRESET_MODE_ECO_STATE,
    ],
)
async def test_modern_turn_on_preset_mode_reverse(
    hass: HomeAssistant, start_state
) -> None:
    """Test modern fan state reproduction, turning on with preset mode "Auto" and reverse direction."""
    hass.states.async_set(MODERN_FAN_ENTITY, "off", start_state)

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_mode = async_mock_service(hass, "fan", "set_percentage")
    set_preset_mode = async_mock_service(hass, "fan", "set_preset_mode")

    await async_reproduce_state(
        hass,
        [State(MODERN_FAN_ENTITY, "on", MODERN_FAN_PRESET_MODE_AUTO_REVERSE_STATE)],
    )

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].domain == "fan"
    assert turn_on_calls[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_PRESET_MODE: "Auto",
    }
    assert len(set_direction_calls) == 1
    assert set_direction_calls[0].domain == "fan"
    assert set_direction_calls[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_DIRECTION: DIRECTION_REVERSE,
    }

    assert len(turn_off_calls) == 0
    assert len(oscillate_calls) == 0
    assert len(set_percentage_mode) == 0
    assert len(set_preset_mode) == 0


@pytest.mark.parametrize(
    "start_state",
    [
        MODERN_FAN_ON_PERCENTAGE10_STATE,
        MODERN_FAN_ON_PERCENTAGE15_STATE,
        MODERN_FAN_ON_PRESET_MODE_ECO_STATE,
    ],
)
async def test_modern_to_preset(hass: HomeAssistant, start_state) -> None:
    """Test modern fan state reproduction, switching to preset mode "Auto"."""
    hass.states.async_set(MODERN_FAN_ENTITY, "on", start_state)

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_mode = async_mock_service(hass, "fan", "set_percentage")
    set_preset_mode = async_mock_service(hass, "fan", "set_preset_mode")

    await async_reproduce_state(
        hass, [State(MODERN_FAN_ENTITY, "on", MODERN_FAN_ON_PRESET_MODE_AUTO_STATE)]
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0
    assert len(set_percentage_mode) == 0
    assert len(set_preset_mode) == 1
    assert set_preset_mode[0].domain == "fan"
    assert set_preset_mode[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_PRESET_MODE: "Auto",
    }


@pytest.mark.parametrize(
    "start_state",
    [
        MODERN_FAN_ON_PERCENTAGE10_STATE,
        MODERN_FAN_ON_PRESET_MODE_AUTO_STATE,
        MODERN_FAN_ON_PRESET_MODE_ECO_STATE,
    ],
)
async def test_modern_to_percentage(hass: HomeAssistant, start_state) -> None:
    """Test modern fan state reproduction, switching to 15% speed."""
    hass.states.async_set(MODERN_FAN_ENTITY, "on", start_state)

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_mode = async_mock_service(hass, "fan", "set_percentage")
    set_preset_mode = async_mock_service(hass, "fan", "set_preset_mode")

    await async_reproduce_state(
        hass, [State(MODERN_FAN_ENTITY, "on", MODERN_FAN_ON_PERCENTAGE15_STATE)]
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 0
    assert len(oscillate_calls) == 0
    assert len(set_percentage_mode) == 1
    assert set_percentage_mode[0].domain == "fan"
    assert set_percentage_mode[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_PERCENTAGE: 15,
    }
    assert len(set_preset_mode) == 0


async def test_modern_direction(hass: HomeAssistant) -> None:
    """Test modern fan state reproduction, switching only direction state."""
    hass.states.async_set(MODERN_FAN_ENTITY, "on", MODERN_FAN_ON_PRESET_MODE_AUTO_STATE)

    turn_on_calls = async_mock_service(hass, "fan", "turn_on")
    turn_off_calls = async_mock_service(hass, "fan", "turn_off")
    set_direction_calls = async_mock_service(hass, "fan", "set_direction")
    oscillate_calls = async_mock_service(hass, "fan", "oscillate")
    set_percentage_mode = async_mock_service(hass, "fan", "set_percentage")
    set_preset_mode = async_mock_service(hass, "fan", "set_preset_mode")

    await async_reproduce_state(
        hass,
        [State(MODERN_FAN_ENTITY, "on", MODERN_FAN_PRESET_MODE_AUTO_REVERSE_STATE)],
    )

    assert len(turn_on_calls) == 0
    assert len(turn_off_calls) == 0
    assert len(set_direction_calls) == 1
    assert set_direction_calls[0].domain == "fan"
    assert set_direction_calls[0].data == {
        "entity_id": MODERN_FAN_ENTITY,
        ATTR_DIRECTION: DIRECTION_REVERSE,
    }
    assert len(oscillate_calls) == 0
    assert len(set_percentage_mode) == 0
    assert len(set_preset_mode) == 0
