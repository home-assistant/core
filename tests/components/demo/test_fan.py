"""Test cases around the demo fan platform."""

from unittest.mock import patch

import pytest

from homeassistant.components import fan
from homeassistant.components.demo.fan import (
    PRESET_MODE_AUTO,
    PRESET_MODE_ON,
    PRESET_MODE_SLEEP,
    PRESET_MODE_SMART,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

FULL_FAN_ENTITY_IDS = ["fan.living_room_fan", "fan.percentage_full_fan"]
FANS_WITH_PRESET_MODE_ONLY = ["fan.preset_only_limited_fan"]
LIMITED_AND_FULL_FAN_ENTITY_IDS = [
    *FULL_FAN_ENTITY_IDS,
    "fan.ceiling_fan",
    "fan.percentage_limited_fan",
]
FANS_WITH_PRESET_MODES = [*FULL_FAN_ENTITY_IDS, "fan.percentage_limited_fan"]
PERCENTAGE_MODEL_FANS = ["fan.percentage_full_fan", "fan.percentage_limited_fan"]


@pytest.fixture
async def fan_only() -> None:
    """Enable only the datetime platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.FAN],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, fan_only: None):
    """Initialize components."""
    assert await async_setup_component(hass, fan.DOMAIN, {"fan": {"platform": "demo"}})
    await hass.async_block_till_done()


@pytest.mark.parametrize("fan_entity_id", LIMITED_AND_FULL_FAN_ENTITY_IDS)
async def test_turn_on(hass: HomeAssistant, fan_entity_id) -> None:
    """Test turning on the device."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: fan_entity_id}, blocking=True
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON


@pytest.mark.parametrize("fan_entity_id", FULL_FAN_ENTITY_IDS)
async def test_turn_on_with_speed_and_percentage(
    hass: HomeAssistant, fan_entity_id
) -> None:
    """Test turning on the device."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 100

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE: 66},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 66

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE: 33},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 33

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 100

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE: 66},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 66

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE: 33},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 33

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PERCENTAGE] == 0


@pytest.mark.parametrize("fan_entity_id", FANS_WITH_PRESET_MODE_ONLY)
async def test_turn_on_with_preset_mode_only(
    hass: HomeAssistant, fan_entity_id
) -> None:
    """Test turning on the device with a preset_mode and no speed setting."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PRESET_MODE: PRESET_MODE_AUTO},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PRESET_MODE] == PRESET_MODE_AUTO
    assert state.attributes[fan.ATTR_PRESET_MODES] == [
        PRESET_MODE_AUTO,
        PRESET_MODE_SMART,
        PRESET_MODE_SLEEP,
        PRESET_MODE_ON,
    ]

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PRESET_MODE: PRESET_MODE_SMART},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PRESET_MODE] == PRESET_MODE_SMART

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: fan_entity_id}, blocking=True
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PRESET_MODE] is None

    with pytest.raises(fan.NotValidPresetModeError) as exc:
        await hass.services.async_call(
            fan.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PRESET_MODE: "invalid"},
            blocking=True,
        )
        await hass.async_block_till_done()
    assert exc.value.translation_domain == fan.DOMAIN
    assert exc.value.translation_key == "not_valid_preset_mode"
    assert exc.value.translation_placeholders == {
        "preset_mode": "invalid",
        "preset_modes": "auto, smart, sleep, on",
    }

    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PRESET_MODE] is None


@pytest.mark.parametrize("fan_entity_id", FANS_WITH_PRESET_MODES)
async def test_turn_on_with_preset_mode_and_speed(
    hass: HomeAssistant, fan_entity_id
) -> None:
    """Test turning on the device with a preset_mode and speed."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PRESET_MODE: PRESET_MODE_AUTO},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] is None
    assert state.attributes[fan.ATTR_PRESET_MODE] == PRESET_MODE_AUTO
    assert state.attributes[fan.ATTR_PRESET_MODES] == [
        PRESET_MODE_AUTO,
        PRESET_MODE_SMART,
        PRESET_MODE_SLEEP,
        PRESET_MODE_ON,
    ]

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] == 100
    assert state.attributes[fan.ATTR_PRESET_MODE] is None

    await hass.services.async_call(
        fan.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PRESET_MODE: PRESET_MODE_SMART},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] is None
    assert state.attributes[fan.ATTR_PRESET_MODE] == PRESET_MODE_SMART

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: fan_entity_id}, blocking=True
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PERCENTAGE] == 0
    assert state.attributes[fan.ATTR_PRESET_MODE] is None

    with pytest.raises(fan.NotValidPresetModeError) as exc:
        await hass.services.async_call(
            fan.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PRESET_MODE: "invalid"},
            blocking=True,
        )
        await hass.async_block_till_done()
    assert exc.value.translation_domain == fan.DOMAIN
    assert exc.value.translation_key == "not_valid_preset_mode"
    assert exc.value.translation_placeholders == {
        "preset_mode": "invalid",
        "preset_modes": "auto, smart, sleep, on",
    }

    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PERCENTAGE] == 0
    assert state.attributes[fan.ATTR_PRESET_MODE] is None


@pytest.mark.parametrize("fan_entity_id", LIMITED_AND_FULL_FAN_ENTITY_IDS)
async def test_turn_off(hass: HomeAssistant, fan_entity_id) -> None:
    """Test turning off the device."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: fan_entity_id}, blocking=True
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: fan_entity_id}, blocking=True
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF


@pytest.mark.parametrize("fan_entity_id", LIMITED_AND_FULL_FAN_ENTITY_IDS)
async def test_turn_off_without_entity_id(hass: HomeAssistant, fan_entity_id) -> None:
    """Test turning off all fans."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: fan_entity_id}, blocking=True
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_MATCH_ALL}, blocking=True
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF


@pytest.mark.parametrize("fan_entity_id", FULL_FAN_ENTITY_IDS)
async def test_set_direction(hass: HomeAssistant, fan_entity_id) -> None:
    """Test setting the direction of the device."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_SET_DIRECTION,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_DIRECTION: fan.DIRECTION_REVERSE},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_DIRECTION] == fan.DIRECTION_REVERSE


@pytest.mark.parametrize("fan_entity_id", FANS_WITH_PRESET_MODES)
async def test_set_preset_mode(hass: HomeAssistant, fan_entity_id) -> None:
    """Test setting the preset mode of the device."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PRESET_MODE: PRESET_MODE_AUTO},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_ON
    assert state.attributes[fan.ATTR_PERCENTAGE] is None
    assert state.attributes[fan.ATTR_PRESET_MODE] == PRESET_MODE_AUTO


@pytest.mark.parametrize("fan_entity_id", LIMITED_AND_FULL_FAN_ENTITY_IDS)
async def test_set_preset_mode_invalid(hass: HomeAssistant, fan_entity_id) -> None:
    """Test setting a invalid preset mode for the device."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF

    with pytest.raises(fan.NotValidPresetModeError) as exc:
        await hass.services.async_call(
            fan.DOMAIN,
            fan.SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PRESET_MODE: "invalid"},
            blocking=True,
        )
        await hass.async_block_till_done()
    assert exc.value.translation_domain == fan.DOMAIN
    assert exc.value.translation_key == "not_valid_preset_mode"

    with pytest.raises(fan.NotValidPresetModeError) as exc:
        await hass.services.async_call(
            fan.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PRESET_MODE: "invalid"},
            blocking=True,
        )
        await hass.async_block_till_done()
    assert exc.value.translation_domain == fan.DOMAIN
    assert exc.value.translation_key == "not_valid_preset_mode"


@pytest.mark.parametrize("fan_entity_id", FULL_FAN_ENTITY_IDS)
async def test_set_percentage(hass: HomeAssistant, fan_entity_id) -> None:
    """Test setting the percentage speed of the device."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE: 33},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 33


@pytest.mark.parametrize("fan_entity_id", LIMITED_AND_FULL_FAN_ENTITY_IDS)
async def test_increase_decrease_speed(hass: HomeAssistant, fan_entity_id) -> None:
    """Test increasing and decreasing the percentage speed of the device."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[fan.ATTR_PERCENTAGE_STEP] == 100 / 3

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 33

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 66

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 100

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 100

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 66

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 33

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 0

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_DECREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 0


@pytest.mark.parametrize("fan_entity_id", PERCENTAGE_MODEL_FANS)
async def test_increase_decrease_speed_with_percentage_step(
    hass: HomeAssistant, fan_entity_id
) -> None:
    """Test increasing speed with a percentage step."""
    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE_STEP: 25},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 25

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE_STEP: 25},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 50

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_INCREASE_SPEED,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_PERCENTAGE_STEP: 25},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_PERCENTAGE] == 75


@pytest.mark.parametrize("fan_entity_id", FULL_FAN_ENTITY_IDS)
async def test_oscillate(hass: HomeAssistant, fan_entity_id) -> None:
    """Test oscillating the fan."""
    state = hass.states.get(fan_entity_id)
    assert state.state == STATE_OFF
    assert not state.attributes.get(fan.ATTR_OSCILLATING)

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_OSCILLATING: True},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_OSCILLATING] is True

    await hass.services.async_call(
        fan.DOMAIN,
        fan.SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: fan_entity_id, fan.ATTR_OSCILLATING: False},
        blocking=True,
    )
    state = hass.states.get(fan_entity_id)
    assert state.attributes[fan.ATTR_OSCILLATING] is False


@pytest.mark.parametrize("fan_entity_id", LIMITED_AND_FULL_FAN_ENTITY_IDS)
async def test_is_on(hass: HomeAssistant, fan_entity_id) -> None:
    """Test is on service call."""
    assert not fan.is_on(hass, fan_entity_id)

    await hass.services.async_call(
        fan.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: fan_entity_id}, blocking=True
    )
    assert fan.is_on(hass, fan_entity_id)
