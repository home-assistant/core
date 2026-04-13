"""The tests for the Template fan platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import fan, template
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntityFeature,
    NotValidPresetModeError,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    async_get_flow_preview_state,
    async_trigger,
    make_test_action,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
)

from tests.common import MockConfigEntry
from tests.components.fan import common
from tests.typing import WebSocketGenerator

TEST_INPUT_BOOLEAN = "input_boolean.state"
TEST_STATE_ENTITY_ID = "sensor.test_sensor"
TEST_AVAILABILITY_ENTITY = "binary_sensor.availability"

TEST_FAN = TemplatePlatformSetup(
    fan.DOMAIN,
    "fans",
    "test_fan",
    make_test_trigger(
        TEST_INPUT_BOOLEAN, TEST_STATE_ENTITY_ID, TEST_AVAILABILITY_ENTITY
    ),
)

ON_ACTION = make_test_action("turn_on")
OFF_ACTION = make_test_action("turn_off")

OPTIMISTIC_ON_OFF_ACTIONS = {
    **ON_ACTION,
    **OFF_ACTION,
}

PERCENTAGE_ACTION = make_test_action(
    "set_percentage", {"percentage": "{{ percentage }}"}
)
OPTIMISTIC_PERCENTAGE_CONFIG = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    **PERCENTAGE_ACTION,
}

PRESET_MODE_ACTION = make_test_action(
    "set_preset_mode", {"preset_mode": "{{ preset_mode }}"}
)
OPTIMISTIC_PRESET_MODE_CONFIG = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    **PRESET_MODE_ACTION,
}
OPTIMISTIC_PRESET_MODE_CONFIG2 = {
    **OPTIMISTIC_PRESET_MODE_CONFIG,
    "preset_modes": ["auto", "low", "medium", "high"],
}

OSCILLATE_ACTION = make_test_action(
    "set_oscillating", {"oscillating": "{{ oscillating }}"}
)
OPTIMISTIC_OSCILLATE_CONFIG = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    **OSCILLATE_ACTION,
}

DIRECTION_ACTION = make_test_action("set_direction", {"direction": "{{ direction }}"})
OPTIMISTIC_DIRECTION_CONFIG = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    **DIRECTION_ACTION,
}


def _verify(
    hass: HomeAssistant,
    expected_state: str,
    expected_percentage: int | None = None,
    expected_oscillating: bool | None = None,
    expected_direction: str | None = None,
    expected_preset_mode: str | None = None,
) -> None:
    """Verify fan's state, speed and osc."""
    state = hass.states.get(TEST_FAN.entity_id)
    attributes = state.attributes
    assert state.state == str(expected_state)
    assert attributes.get(ATTR_PERCENTAGE) == expected_percentage
    assert attributes.get(ATTR_OSCILLATING) == expected_oscillating
    assert attributes.get(ATTR_DIRECTION) == expected_direction
    assert attributes.get(ATTR_PRESET_MODE) == expected_preset_mode


@pytest.fixture
async def setup_fan(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType,
    extra_config: ConfigType,
) -> None:
    """Do setup of fan integration."""
    await setup_entity(hass, TEST_FAN, style, count, config, extra_config=extra_config)


@pytest.fixture
async def setup_state_fan(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    extra_config: ConfigType,
):
    """Do setup of fan integration using a state template."""
    await setup_entity(hass, TEST_FAN, style, count, extra_config, state_template)


@pytest.fixture
async def setup_optimistic_fan_attribute(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    extra_config: dict,
) -> None:
    """Do setup of a non-optimistic fan with an optimistic attribute."""
    await setup_entity(
        hass, TEST_FAN, style, count, {}, "{{ 1==1 }}", extra_config=extra_config
    )


@pytest.fixture
async def setup_single_attribute_state_fan(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    attribute: str,
    attribute_template: str,
    state_template: str,
    extra_config: dict,
) -> None:
    """Do setup of fan integration testing a single attribute."""
    await setup_entity(
        hass,
        TEST_FAN,
        style,
        count,
        {attribute: attribute_template} if attribute and attribute_template else {},
        state_template,
        {**OPTIMISTIC_ON_OFF_ACTIONS, **extra_config},
    )


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", OPTIMISTIC_ON_OFF_ACTIONS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_missing_optional_config(hass: HomeAssistant) -> None:
    """Test: missing optional template is ok."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
    _verify(hass, STATE_ON, None, None, None, None)


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "extra_config",
    [OFF_ACTION, ON_ACTION],
)
@pytest.mark.usefixtures("setup_optimistic_fan_attribute")
async def test_wrong_template_config(hass: HomeAssistant) -> None:
    """Test: missing 'turn_on' or 'turn_off' will fail."""
    assert hass.states.async_all("fan") == []


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ is_state('input_boolean.state', 'on') }}", OPTIMISTIC_ON_OFF_ACTIONS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_state_template(hass: HomeAssistant) -> None:
    """Test state template."""
    await async_trigger(hass, TEST_INPUT_BOOLEAN, STATE_OFF)
    _verify(hass, STATE_OFF, None, None, None, None)

    await async_trigger(hass, TEST_INPUT_BOOLEAN, STATE_ON)
    _verify(hass, STATE_ON, None, None, None, None)

    await async_trigger(hass, TEST_INPUT_BOOLEAN, STATE_OFF)
    _verify(hass, STATE_OFF, None, None, None, None)


@pytest.mark.parametrize(("count", "extra_config"), [(1, OPTIMISTIC_ON_OFF_ACTIONS)])
@pytest.mark.parametrize(
    ("state_template", "expected"),
    [
        ("{{ True }}", STATE_ON),
        ("{{ False }}", STATE_OFF),
        ("{{ x - 1 }}", STATE_UNAVAILABLE),
        ("{{ 1 }}", STATE_ON),
        ("{{ 'true' }}", STATE_ON),
        ("{{ 'yes' }}", STATE_ON),
        ("{{ 'on' }}", STATE_ON),
        ("{{ 'enable' }}", STATE_ON),
        ("{{ 0 }}", STATE_OFF),
        ("{{ 'false' }}", STATE_OFF),
        ("{{ 'no' }}", STATE_OFF),
        ("{{ 'off' }}", STATE_OFF),
        ("{{ 'disable' }}", STATE_OFF),
        ("{{ None }}", STATE_UNKNOWN),
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_state_template_states(hass: HomeAssistant, expected: str) -> None:
    """Test state template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
    _verify(hass, expected, None, None, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config", "attribute"),
    [
        (
            1,
            "{{ 1 == 1}}",
            "{% if is_state('sensor.test_sensor', 'on') %}/local/switch.png{% endif %}",
            {},
            "picture",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_state_fan")
async def test_picture_template(hass: HomeAssistant) -> None:
    """Test picture template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.attributes.get("entity_picture") == ""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.attributes["entity_picture"] == "/local/switch.png"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config", "attribute"),
    [
        (
            1,
            "{{ 1 == 1}}",
            "{% if states.input_boolean.state.state %}mdi:eye{% endif %}",
            {},
            "icon",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_state_fan")
async def test_icon_template(hass: HomeAssistant) -> None:
    """Test icon template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.attributes.get("icon") == ""

    await async_trigger(hass, TEST_INPUT_BOOLEAN, STATE_ON)

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.attributes["icon"] == "mdi:eye"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ states('sensor.test_sensor') }}",
            PERCENTAGE_ACTION,
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "percentage_template"),
        (ConfigurationStyle.MODERN, "percentage"),
        (ConfigurationStyle.TRIGGER, "percentage"),
    ],
)
@pytest.mark.parametrize(
    ("percent", "expected"),
    [
        ("0", 0),
        ("33", 33),
        ("invalid", None),
        ("5000", None),
        ("100", 100),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_fan")
async def test_percentage_template(
    hass: HomeAssistant, percent: str, expected: int
) -> None:
    """Test templates with fan percentages from other entities."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, percent)
    _verify(hass, STATE_ON, expected, None, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ states('sensor.test_sensor') }}",
            {"preset_modes": ["auto", "smart"], **PRESET_MODE_ACTION},
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "preset_mode_template"),
        (ConfigurationStyle.MODERN, "preset_mode"),
        (ConfigurationStyle.TRIGGER, "preset_mode"),
    ],
)
@pytest.mark.parametrize(
    ("preset_mode", "expected"),
    [
        ("0", None),
        ("invalid", None),
        ("auto", "auto"),
        ("smart", "smart"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_fan")
async def test_preset_mode_template(
    hass: HomeAssistant, preset_mode: str, expected: int
) -> None:
    """Test preset_mode template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, preset_mode)
    _verify(hass, STATE_ON, None, None, None, expected)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ is_state('sensor.test_sensor', 'on') }}",
            OSCILLATE_ACTION,
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "oscillating_template"),
        (ConfigurationStyle.MODERN, "oscillating"),
        (ConfigurationStyle.TRIGGER, "oscillating"),
    ],
)
@pytest.mark.parametrize(
    ("oscillating", "expected"),
    [
        (STATE_ON, True),
        (STATE_OFF, False),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_fan")
async def test_oscillating_template(
    hass: HomeAssistant, oscillating: str, expected: bool | None
) -> None:
    """Test oscillating template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, oscillating)
    _verify(hass, STATE_ON, None, expected, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ states('sensor.test_sensor') }}",
            DIRECTION_ACTION,
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "direction_template"),
        (ConfigurationStyle.MODERN, "direction"),
        (ConfigurationStyle.TRIGGER, "direction"),
    ],
)
@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        (DIRECTION_FORWARD, DIRECTION_FORWARD),
        (DIRECTION_REVERSE, DIRECTION_REVERSE),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_fan")
async def test_direction_template(
    hass: HomeAssistant, direction: str, expected: bool | None
) -> None:
    """Test direction template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, direction)
    _verify(hass, STATE_ON, None, None, expected, None)


@pytest.mark.parametrize(("count", "extra_config"), [(1, {})])
@pytest.mark.parametrize(
    ("style", "config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "availability_template": (
                    "{{ is_state('binary_sensor.availability', 'on') }}"
                ),
                "value_template": "{{ 'on' }}",
                "oscillating_template": "{{ 1 == 1 }}",
                "direction_template": "{{ 'forward' }}",
                "turn_on": {"service": "script.fan_on"},
                "turn_off": {"service": "script.fan_off"},
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "availability": ("{{ is_state('binary_sensor.availability', 'on') }}"),
                "state": "{{ 'on' }}",
                "oscillating": "{{ 1 == 1 }}",
                "direction": "{{ 'forward' }}",
                "turn_on": {"service": "script.fan_on"},
                "turn_off": {"service": "script.fan_off"},
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "availability": ("{{ is_state('binary_sensor.availability', 'on') }}"),
                "state": "{{ 'on' }}",
                "oscillating": "{{ 1 == 1 }}",
                "direction": "{{ 'forward' }}",
                "turn_on": {"service": "script.fan_on"},
                "turn_off": {"service": "script.fan_off"},
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_fan")
async def test_availability_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability tempalates with values from other entities."""
    for state, test_assert in ((STATE_ON, True), (STATE_OFF, False)):
        await async_trigger(hass, TEST_AVAILABILITY_ENTITY, state)
        assert (
            hass.states.get(TEST_FAN.entity_id).state != STATE_UNAVAILABLE
        ) == test_assert


@pytest.mark.parametrize(("count", "extra_config"), [(1, {})])
@pytest.mark.parametrize(
    ("style", "config", "states"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'unavailable' }}",
                **OPTIMISTIC_ON_OFF_ACTIONS,
            },
            [STATE_UNKNOWN, None, None, None],
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'unavailable' }}",
                **OPTIMISTIC_ON_OFF_ACTIONS,
            },
            [STATE_UNKNOWN, None, None, None],
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "state": "{{ 'unavailable' }}",
                **OPTIMISTIC_ON_OFF_ACTIONS,
            },
            [STATE_UNKNOWN, None, None, None],
        ),
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
                "percentage_template": "{{ 0 }}",
                **OPTIMISTIC_PERCENTAGE_CONFIG,
                "oscillating_template": "{{ 'unavailable' }}",
                **OSCILLATE_ACTION,
                "direction_template": "{{ 'unavailable' }}",
                **DIRECTION_ACTION,
            },
            [STATE_ON, 0, None, None],
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
                "percentage": "{{ 0 }}",
                **OPTIMISTIC_PERCENTAGE_CONFIG,
                "oscillating": "{{ 'unavailable' }}",
                **OSCILLATE_ACTION,
                "direction": "{{ 'unavailable' }}",
                **DIRECTION_ACTION,
            },
            [STATE_ON, 0, None, None],
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "state": "{{ 'on' }}",
                "percentage": "{{ 0 }}",
                **OPTIMISTIC_PERCENTAGE_CONFIG,
                "oscillating": "{{ 'unavailable' }}",
                **OSCILLATE_ACTION,
                "direction": "{{ 'unavailable' }}",
                **DIRECTION_ACTION,
            },
            [STATE_ON, 0, None, None],
        ),
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
                "percentage_template": "{{ 66 }}",
                **OPTIMISTIC_PERCENTAGE_CONFIG,
                "oscillating_template": "{{ 1 == 1 }}",
                **OSCILLATE_ACTION,
                "direction_template": "{{ 'forward' }}",
                **DIRECTION_ACTION,
            },
            [STATE_ON, 66, True, DIRECTION_FORWARD],
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
                "percentage": "{{ 66 }}",
                **OPTIMISTIC_PERCENTAGE_CONFIG,
                "oscillating": "{{ 1 == 1 }}",
                **OSCILLATE_ACTION,
                "direction": "{{ 'forward' }}",
                **DIRECTION_ACTION,
            },
            [STATE_ON, 66, True, DIRECTION_FORWARD],
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "state": "{{ 'on' }}",
                "percentage": "{{ 66 }}",
                **OPTIMISTIC_PERCENTAGE_CONFIG,
                "oscillating": "{{ 1 == 1 }}",
                **OSCILLATE_ACTION,
                "direction": "{{ 'forward' }}",
                **DIRECTION_ACTION,
            },
            [STATE_ON, 66, True, DIRECTION_FORWARD],
        ),
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'abc' }}",
                "percentage_template": "{{ 0 }}",
                **OPTIMISTIC_PERCENTAGE_CONFIG,
                "oscillating_template": "{{ 'xyz' }}",
                **OSCILLATE_ACTION,
                "direction_template": "{{ 'right' }}",
                **DIRECTION_ACTION,
            },
            [STATE_UNKNOWN, 0, None, None],
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'abc' }}",
                "percentage": "{{ 0 }}",
                **OPTIMISTIC_PERCENTAGE_CONFIG,
                "oscillating": "{{ 'xyz' }}",
                **OSCILLATE_ACTION,
                "direction": "{{ 'right' }}",
                **DIRECTION_ACTION,
            },
            [STATE_UNKNOWN, 0, None, None],
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "state": "{{ 'abc' }}",
                "percentage": "{{ 0 }}",
                **OPTIMISTIC_PERCENTAGE_CONFIG,
                "oscillating": "{{ 'xyz' }}",
                **OSCILLATE_ACTION,
                "direction": "{{ 'right' }}",
                **DIRECTION_ACTION,
            },
            [STATE_UNKNOWN, 0, None, None],
        ),
    ],
)
@pytest.mark.usefixtures("setup_fan")
async def test_template_with_unavailable_entities(hass: HomeAssistant, states) -> None:
    """Test unavailability with value_template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
    _verify(hass, states[0], states[1], states[2], states[3], None)


@pytest.mark.parametrize(("count", "extra_config"), [(1, {})])
@pytest.mark.parametrize(
    ("style", "config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
                "availability_template": "{{ x - 12 }}",
                "preset_mode_template": ("{{ states('input_select.preset_mode') }}"),
                "oscillating_template": "{{ states('input_select.osc') }}",
                "direction_template": "{{ states('input_select.direction') }}",
                "turn_on": {"service": "script.fan_on"},
                "turn_off": {"service": "script.fan_off"},
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
                "availability": "{{ x - 12 }}",
                "preset_mode": ("{{ states('input_select.preset_mode') }}"),
                "oscillating": "{{ states('input_select.osc') }}",
                "direction": "{{ states('input_select.direction') }}",
                "turn_on": {"service": "script.fan_on"},
                "turn_off": {"service": "script.fan_off"},
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "state": "{{ 'on' }}",
                "availability": "{{ x - 12 }}",
                "preset_mode": ("{{ states('input_select.preset_mode') }}"),
                "oscillating": "{{ states('input_select.osc') }}",
                "direction": "{{ states('input_select.direction') }}",
                "turn_on": {"service": "script.fan_on"},
                "turn_off": {"service": "script.fan_off"},
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_fan")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid availability keeps the device available."""
    # Ensure trigger entities update.
    await async_trigger(hass, TEST_INPUT_BOOLEAN, STATE_ON)

    assert hass.states.get(TEST_FAN.entity_id).state != STATE_UNAVAILABLE

    err = "'x' is undefined"
    assert err in caplog_setup_text or err in caplog.text


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'off' }}", OPTIMISTIC_ON_OFF_ACTIONS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_on_off(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test turn on and turn off."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.state == STATE_OFF

    for expected_calls, (func, action) in enumerate(
        [
            (common.async_turn_on, "turn_on"),
            (common.async_turn_off, "turn_off"),
        ]
    ):
        await func(hass, TEST_FAN.entity_id)

        assert_action(TEST_FAN, calls, expected_calls + 1, action)


@pytest.mark.parametrize(
    ("count", "extra_config", "state_template"),
    [
        (
            1,
            {
                **OPTIMISTIC_ON_OFF_ACTIONS,
                **OPTIMISTIC_PRESET_MODE_CONFIG2,
                **OPTIMISTIC_PERCENTAGE_CONFIG,
            },
            "{{ 'off' }}",
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_on_with_extra_attributes(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test turn on and turn off."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, TEST_FAN.entity_id, 100)

    assert_action(TEST_FAN, calls, 2, "turn_on", index=-2)
    assert_action(TEST_FAN, calls, 2, "set_percentage", percentage=100)

    await common.async_turn_off(hass, TEST_FAN.entity_id)

    assert_action(TEST_FAN, calls, 3, "turn_off")

    await common.async_turn_on(hass, TEST_FAN.entity_id, None, "auto")

    assert_action(TEST_FAN, calls, 5, "turn_on", index=-2)
    assert_action(TEST_FAN, calls, 5, "set_preset_mode", preset_mode="auto")

    await common.async_turn_off(hass, TEST_FAN.entity_id)

    assert_action(TEST_FAN, calls, 6, "turn_off")

    await common.async_turn_on(hass, TEST_FAN.entity_id, 50, "high")

    assert_action(TEST_FAN, calls, 9, "turn_on", index=-3)
    assert_action(TEST_FAN, calls, 9, "set_preset_mode", index=-2, preset_mode="high")
    assert_action(TEST_FAN, calls, 9, "set_percentage", percentage=50)

    await common.async_turn_off(hass, TEST_FAN.entity_id)

    assert_action(TEST_FAN, calls, 10, "turn_off")


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", {**OPTIMISTIC_ON_OFF_ACTIONS, **DIRECTION_ACTION})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_set_invalid_direction_from_initial_stage(hass: HomeAssistant) -> None:
    """Test set invalid direction when fan is in initial state."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    await common.async_set_direction(hass, TEST_FAN.entity_id, "invalid")
    _verify(hass, STATE_ON, None, None, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", {**OPTIMISTIC_ON_OFF_ACTIONS, **OSCILLATE_ACTION})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_set_osc(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set oscillating."""
    expected_calls = 0

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    await common.async_turn_on(hass, TEST_FAN.entity_id)
    expected_calls += 1
    for state in (True, False):
        await common.async_oscillate(hass, TEST_FAN.entity_id, state)
        _verify(hass, STATE_ON, None, state, None, None)
        expected_calls += 1
        assert_action(
            TEST_FAN, calls, expected_calls, "set_oscillating", oscillating=state
        )


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", {**OPTIMISTIC_ON_OFF_ACTIONS, **DIRECTION_ACTION})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_set_direction(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set valid direction."""
    expected_calls = 0

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    await common.async_turn_on(hass, TEST_FAN.entity_id)
    expected_calls += 1
    for direction in (DIRECTION_FORWARD, DIRECTION_REVERSE):
        await common.async_set_direction(hass, TEST_FAN.entity_id, direction)
        _verify(hass, STATE_ON, None, None, direction, None)
        expected_calls += 1
        assert_action(
            TEST_FAN, calls, expected_calls, "set_direction", direction=direction
        )


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", {**OPTIMISTIC_ON_OFF_ACTIONS, **DIRECTION_ACTION})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_set_invalid_direction(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set invalid direction when fan has valid direction."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    expected_calls = 1
    for direction in (DIRECTION_FORWARD, "invalid"):
        await common.async_set_direction(hass, TEST_FAN.entity_id, direction)
        _verify(hass, STATE_ON, None, None, DIRECTION_FORWARD, None)
        assert_action(
            TEST_FAN,
            calls,
            expected_calls,
            "set_direction",
            direction=DIRECTION_FORWARD,
        )


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", OPTIMISTIC_PRESET_MODE_CONFIG2)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_preset_modes(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test preset_modes."""
    for cnt, mode in enumerate(("auto", "low", "medium", "high")):
        await common.async_set_preset_mode(hass, TEST_FAN.entity_id, mode)
        assert_action(TEST_FAN, calls, cnt + 1, "set_preset_mode", preset_mode=mode)


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", OPTIMISTIC_PRESET_MODE_CONFIG2)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_invalid_preset_modes(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test invalid preset_modes."""
    for mode in ("invalid", "smart"):
        with pytest.raises(NotValidPresetModeError):
            await common.async_set_preset_mode(hass, TEST_FAN.entity_id, mode)


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", OPTIMISTIC_PERCENTAGE_CONFIG)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_set_percentage(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set valid speed percentage."""
    expected_calls = 0

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    await common.async_turn_on(hass, TEST_FAN.entity_id)
    expected_calls += 1
    for state, value in (
        (STATE_ON, 100),
        (STATE_ON, 66),
        (STATE_ON, 0),
    ):
        await common.async_set_percentage(hass, TEST_FAN.entity_id, value)
        _verify(hass, state, value, None, None, None)
        expected_calls += 1
        assert_action(
            TEST_FAN, calls, expected_calls, "set_percentage", percentage=value
        )

    await common.async_turn_on(hass, TEST_FAN.entity_id, percentage=50)
    _verify(hass, STATE_ON, 50, None, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", {"speed_count": 3, **OPTIMISTIC_PERCENTAGE_CONFIG})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_increase_decrease_speed(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set valid increase and decrease speed."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    await common.async_turn_on(hass, TEST_FAN.entity_id)
    for func, extra, state, value in (
        (common.async_set_percentage, 100, STATE_ON, 100),
        (common.async_decrease_speed, None, STATE_ON, 66),
        (common.async_decrease_speed, None, STATE_ON, 33),
        (common.async_decrease_speed, None, STATE_ON, 0),
        (common.async_increase_speed, None, STATE_ON, 33),
    ):
        await func(hass, TEST_FAN.entity_id, extra)
        _verify(hass, state, value, None, None, None)


@pytest.mark.parametrize(
    ("count", "config", "extra_config"),
    [
        (
            1,
            {
                **OPTIMISTIC_ON_OFF_ACTIONS,
                "preset_modes": ["auto"],
                **PRESET_MODE_ACTION,
                **PERCENTAGE_ACTION,
                **OSCILLATE_ACTION,
                **DIRECTION_ACTION,
            },
            {},
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_fan")
async def test_optimistic_state(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test a fan without a value_template."""

    await common.async_turn_on(hass, TEST_FAN.entity_id)
    _verify(hass, STATE_ON)

    assert_action(TEST_FAN, calls, 1, "turn_on")

    await common.async_turn_off(hass, TEST_FAN.entity_id)
    _verify(hass, STATE_OFF)

    assert_action(TEST_FAN, calls, 2, "turn_off")

    percent = 100
    await common.async_set_percentage(hass, TEST_FAN.entity_id, percent)
    _verify(hass, STATE_ON, percent)

    assert_action(TEST_FAN, calls, 3, "set_percentage", percentage=percent)

    await common.async_turn_off(hass, TEST_FAN.entity_id)
    _verify(hass, STATE_OFF, percent)

    assert_action(TEST_FAN, calls, 4, "turn_off")

    preset = "auto"
    await common.async_set_preset_mode(hass, TEST_FAN.entity_id, preset)
    _verify(hass, STATE_ON, percent, None, None, preset)

    assert_action(TEST_FAN, calls, 5, "set_preset_mode", preset_mode=preset)

    await common.async_turn_off(hass, TEST_FAN.entity_id)
    _verify(hass, STATE_OFF, percent, None, None, preset)

    assert_action(TEST_FAN, calls, 6, "turn_off")

    await common.async_set_direction(hass, TEST_FAN.entity_id, DIRECTION_FORWARD)
    _verify(hass, STATE_OFF, percent, None, DIRECTION_FORWARD, preset)

    assert_action(TEST_FAN, calls, 7, "set_direction", direction=DIRECTION_FORWARD)

    await common.async_oscillate(hass, TEST_FAN.entity_id, True)
    _verify(hass, STATE_OFF, percent, True, DIRECTION_FORWARD, preset)

    assert_action(TEST_FAN, calls, 8, "set_oscillating", oscillating=True)


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("extra_config", "attribute", "action", "verify_attr", "coro", "value"),
    [
        (
            OPTIMISTIC_PERCENTAGE_CONFIG,
            "percentage",
            "set_percentage",
            "expected_percentage",
            common.async_set_percentage,
            50,
        ),
        (
            OPTIMISTIC_PRESET_MODE_CONFIG2,
            "preset_mode",
            "set_preset_mode",
            "expected_preset_mode",
            common.async_set_preset_mode,
            "auto",
        ),
        (
            OPTIMISTIC_OSCILLATE_CONFIG,
            "oscillating",
            "set_oscillating",
            "expected_oscillating",
            common.async_oscillate,
            True,
        ),
        (
            OPTIMISTIC_DIRECTION_CONFIG,
            "direction",
            "set_direction",
            "expected_direction",
            common.async_set_direction,
            DIRECTION_FORWARD,
        ),
    ],
)
@pytest.mark.usefixtures("setup_optimistic_fan_attribute")
async def test_optimistic_attributes(
    hass: HomeAssistant,
    attribute: str,
    action: str,
    verify_attr: str,
    coro,
    value: Any,
    calls: list[ServiceCall],
) -> None:
    """Test setting percentage with optimistic template."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    await coro(hass, TEST_FAN.entity_id, value)
    _verify(hass, STATE_ON, **{verify_attr: value})

    assert_action(TEST_FAN, calls, 1, action, **{attribute: value})


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", OPTIMISTIC_PERCENTAGE_CONFIG)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_increase_decrease_speed_default_speed_count(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set valid increase and decrease speed."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
    await common.async_turn_on(hass, TEST_FAN.entity_id)
    for func, extra, state, value in (
        (common.async_set_percentage, 100, STATE_ON, 100),
        (common.async_decrease_speed, None, STATE_ON, 99),
        (common.async_decrease_speed, None, STATE_ON, 98),
        (common.async_decrease_speed, 31, STATE_ON, 67),
        (common.async_decrease_speed, None, STATE_ON, 66),
    ):
        await func(hass, TEST_FAN.entity_id, extra)
        _verify(hass, state, value, None, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", {**OPTIMISTIC_ON_OFF_ACTIONS, **OSCILLATE_ACTION})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_set_invalid_osc_from_initial_state(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set invalid oscillating when fan is in initial state."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
    await common.async_turn_on(hass, TEST_FAN.entity_id)
    with pytest.raises(vol.Invalid):
        await common.async_oscillate(hass, TEST_FAN.entity_id, "invalid")
    _verify(hass, STATE_ON, None, None, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 'on' }}", {**OPTIMISTIC_ON_OFF_ACTIONS, **OSCILLATE_ACTION})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_set_invalid_osc(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set invalid oscillating when fan has valid osc."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")
    await common.async_turn_on(hass, TEST_FAN.entity_id)
    await common.async_oscillate(hass, TEST_FAN.entity_id, True)
    _verify(hass, STATE_ON, None, True, None, None)

    await common.async_oscillate(hass, TEST_FAN.entity_id, False)
    _verify(hass, STATE_ON, None, False, None, None)

    with pytest.raises(vol.Invalid):
        await common.async_oscillate(hass, TEST_FAN.entity_id, None)
    _verify(hass, STATE_ON, None, False, None, None)


@pytest.mark.parametrize("config", [OPTIMISTIC_ON_OFF_ACTIONS])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant, style: ConfigurationStyle, config: ConfigType
) -> None:
    """Test unique_id option only creates one fan per id."""
    await setup_and_test_unique_id(hass, TEST_FAN, style, config)


@pytest.mark.parametrize("config", [OPTIMISTIC_ON_OFF_ACTIONS])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to fan unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_FAN, style, entity_registry, config
    )


@pytest.mark.parametrize(
    ("count", "extra_config"),
    [(1, {**OPTIMISTIC_ON_OFF_ACTIONS, **OPTIMISTIC_PERCENTAGE_CONFIG})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("config", "percentage_step"),
    [({"speed_count": 0}, 1), ({"speed_count": 100}, 1), ({"speed_count": 3}, 100 / 3)],
)
@pytest.mark.usefixtures("setup_fan")
async def test_speed_percentage_step(hass: HomeAssistant, percentage_step) -> None:
    """Test a fan that implements percentage."""
    assert len(hass.states.async_all()) == 1

    state = hass.states.get(TEST_FAN.entity_id)
    attributes = state.attributes
    assert attributes["percentage_step"] == percentage_step
    assert attributes.get("supported_features") & FanEntityFeature.SET_SPEED


@pytest.mark.parametrize(
    ("count", "config", "extra_config"),
    [(1, OPTIMISTIC_ON_OFF_ACTIONS, OPTIMISTIC_PRESET_MODE_CONFIG2)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_fan")
async def test_preset_mode_supported_features(hass: HomeAssistant) -> None:
    """Test a fan that implements preset_mode."""
    assert len(hass.states.async_all()) == 1

    state = hass.states.get(TEST_FAN.entity_id)
    attributes = state.attributes
    assert attributes.get("supported_features") & FanEntityFeature.PRESET_MODE


@pytest.mark.parametrize(
    ("count", "config"),
    [(1, {"turn_on": [], "turn_off": []})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("extra_config", "supported_features"),
    [
        (
            {
                "set_percentage": [],
            },
            FanEntityFeature.SET_SPEED,
        ),
        (
            {
                "set_preset_mode": [],
            },
            FanEntityFeature.PRESET_MODE,
        ),
        (
            {
                "set_oscillating": [],
            },
            FanEntityFeature.OSCILLATE,
        ),
        (
            {
                "set_direction": [],
            },
            FanEntityFeature.DIRECTION,
        ),
    ],
)
@pytest.mark.usefixtures("setup_fan")
async def test_empty_action_config(
    hass: HomeAssistant,
    supported_features: FanEntityFeature,
) -> None:
    """Test configuration with empty script."""
    state = hass.states.get(TEST_FAN.entity_id)
    assert state.attributes["supported_features"] == (
        FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON | supported_features
    )


@pytest.mark.parametrize(
    ("count", "config", "extra_config"),
    [
        (
            1,
            {
                "state": "{{ is_state('sensor.test_sensor', 'on') }}",
                "turn_on": [],
                "turn_off": [],
                "optimistic": True,
            },
            {},
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_fan")
async def test_optimistic_option(hass: HomeAssistant) -> None:
    """Test optimistic yaml option."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        fan.DOMAIN,
        "turn_on",
        {"entity_id": TEST_FAN.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.state == STATE_ON

    # The double trigger is needed because the state machine
    # suppresses 'off' -> 'off' state changes for TEST_STATE_ENTITY_ID
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("count", "config", "extra_config"),
    [
        (
            1,
            {
                "state": "{{ is_state('sensor.test_sensor', 'on') }}",
                "turn_on": [],
                "turn_off": [],
                "optimistic": False,
            },
            {},
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_fan")
async def test_not_optimistic(hass: HomeAssistant) -> None:
    """Test optimistic yaml option set to false."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    await hass.services.async_call(
        fan.DOMAIN,
        "turn_on",
        {"entity_id": TEST_FAN.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_FAN.entity_id)
    assert state.state == STATE_OFF


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests creating a fan from a config entry."""

    hass.states.async_set(
        "sensor.test_sensor",
        "on",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ states('sensor.test_sensor') }}",
            "turn_on": [],
            "turn_off": [],
            "template_type": fan.DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("fan.my_template")
    assert state is not None
    assert state == snapshot


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        fan.DOMAIN,
        {
            "name": "My template",
            "state": "{{ 'on' }}",
            "turn_on": [],
            "turn_off": [],
        },
    )

    assert state["state"] == STATE_ON
