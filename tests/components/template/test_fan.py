"""The tests for the Template fan platform."""

from typing import Any

import pytest
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
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import ConfigurationStyle

from tests.common import assert_setup_component
from tests.components.fan import common

TEST_OBJECT_ID = "test_fan"
TEST_ENTITY_ID = f"fan.{TEST_OBJECT_ID}"
# Represent for fan's state
_STATE_INPUT_BOOLEAN = "input_boolean.state"
# Represent for fan's state
_STATE_AVAILABILITY_BOOLEAN = "availability_boolean.state"

OPTIMISTIC_ON_OFF_ACTIONS = {
    "turn_on": {
        "service": "test.automation",
        "data": {
            "action": "turn_on",
            "caller": "{{ this.entity_id }}",
        },
    },
    "turn_off": {
        "service": "test.automation",
        "data": {
            "action": "turn_off",
            "caller": "{{ this.entity_id }}",
        },
    },
}
NAMED_ON_OFF_ACTIONS = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    "name": TEST_OBJECT_ID,
}

PERCENTAGE_ACTION = {
    "set_percentage": {
        "action": "test.automation",
        "data": {
            "action": "set_percentage",
            "percentage": "{{ percentage }}",
            "caller": "{{ this.entity_id }}",
        },
    },
}
OPTIMISTIC_PERCENTAGE_CONFIG = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    **PERCENTAGE_ACTION,
}

PRESET_MODE_ACTION = {
    "set_preset_mode": {
        "action": "test.automation",
        "data": {
            "action": "set_preset_mode",
            "preset_mode": "{{ preset_mode }}",
            "caller": "{{ this.entity_id }}",
        },
    },
}
OPTIMISTIC_PRESET_MODE_CONFIG = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    **PRESET_MODE_ACTION,
}
OPTIMISTIC_PRESET_MODE_CONFIG2 = {
    **OPTIMISTIC_PRESET_MODE_CONFIG,
    "preset_modes": ["auto", "low", "medium", "high"],
}

OSCILLATE_ACTION = {
    "set_oscillating": {
        "action": "test.automation",
        "data": {
            "action": "set_oscillating",
            "oscillating": "{{ oscillating }}",
            "caller": "{{ this.entity_id }}",
        },
    },
}
OPTIMISTIC_OSCILLATE_CONFIG = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    **OSCILLATE_ACTION,
}

DIRECTION_ACTION = {
    "set_direction": {
        "action": "test.automation",
        "data": {
            "action": "set_direction",
            "direction": "{{ direction }}",
            "caller": "{{ this.entity_id }}",
        },
    },
}
OPTIMISTIC_DIRECTION_CONFIG = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    **DIRECTION_ACTION,
}
UNIQUE_ID_CONFIG = {
    **OPTIMISTIC_ON_OFF_ACTIONS,
    "unique_id": "not-so-unique-anymore",
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
    state = hass.states.get(TEST_ENTITY_ID)
    attributes = state.attributes
    assert state.state == str(expected_state)
    assert attributes.get(ATTR_PERCENTAGE) == expected_percentage
    assert attributes.get(ATTR_OSCILLATING) == expected_oscillating
    assert attributes.get(ATTR_DIRECTION) == expected_direction
    assert attributes.get(ATTR_PRESET_MODE) == expected_preset_mode


async def async_setup_legacy_format(
    hass: HomeAssistant, count: int, fan_config: dict[str, Any]
) -> None:
    """Do setup of fan integration via legacy format."""
    config = {"fan": {"platform": "template", "fans": fan_config}}

    with assert_setup_component(count, fan.DOMAIN):
        assert await async_setup_component(
            hass,
            fan.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_modern_format(
    hass: HomeAssistant, count: int, fan_config: dict[str, Any]
) -> None:
    """Do setup of fan integration via modern format."""
    config = {"template": {"fan": fan_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_legacy_named_fan(
    hass: HomeAssistant, count: int, fan_config: dict[str, Any]
):
    """Do setup of a named fan via legacy format."""
    await async_setup_legacy_format(hass, count, {TEST_OBJECT_ID: fan_config})


async def async_setup_modern_named_fan(
    hass: HomeAssistant, count: int, fan_config: dict[str, Any]
):
    """Do setup of a named fan via legacy format."""
    await async_setup_modern_format(hass, count, {"name": TEST_OBJECT_ID, **fan_config})


async def async_setup_legacy_format_with_attribute(
    hass: HomeAssistant,
    count: int,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of a legacy fan that has a single templated attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    await async_setup_legacy_format(
        hass,
        count,
        {
            TEST_OBJECT_ID: {
                **extra_config,
                "value_template": "{{ 1 == 1 }}",
                **extra,
            }
        },
    )


async def async_setup_modern_format_with_attribute(
    hass: HomeAssistant,
    count: int,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of a modern fan that has a single templated attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    await async_setup_modern_format(
        hass,
        count,
        {
            "name": TEST_OBJECT_ID,
            **extra_config,
            "state": "{{ 1 == 1 }}",
            **extra,
        },
    )


@pytest.fixture
async def setup_fan(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    fan_config: dict[str, Any],
) -> None:
    """Do setup of fan integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(hass, count, fan_config)
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, fan_config)


@pytest.fixture
async def setup_named_fan(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    fan_config: dict[str, Any],
) -> None:
    """Do setup of fan integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_named_fan(hass, count, fan_config)
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_named_fan(hass, count, fan_config)


@pytest.fixture
async def setup_state_fan(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of fan integration using a state template."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **OPTIMISTIC_ON_OFF_ACTIONS,
                    "value_template": state_template,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                **NAMED_ON_OFF_ACTIONS,
                "state": state_template,
            },
        )


@pytest.fixture
async def setup_test_fan_with_extra_config(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    fan_config: dict[str, Any],
    extra_config: dict[str, Any],
) -> None:
    """Do setup of fan integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass, count, {TEST_OBJECT_ID: {**fan_config, **extra_config}}
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass, count, {"name": TEST_OBJECT_ID, **fan_config, **extra_config}
        )


@pytest.fixture
async def setup_optimistic_fan_attribute(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    extra_config: dict,
) -> None:
    """Do setup of a non-optimistic fan with an optimistic attribute."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format_with_attribute(
            hass, count, "", "", extra_config
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format_with_attribute(
            hass, count, "", "", extra_config
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
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **OPTIMISTIC_ON_OFF_ACTIONS,
                    "value_template": state_template,
                    **extra,
                    **extra_config,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                **NAMED_ON_OFF_ACTIONS,
                "state": state_template,
                **extra,
                **extra_config,
            },
        )


@pytest.mark.parametrize(("count", "state_template"), [(1, "{{ 'on' }}")])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_missing_optional_config(hass: HomeAssistant) -> None:
    """Test: missing optional template is ok."""
    _verify(hass, STATE_ON, None, None, None, None)


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.parametrize(
    "fan_config",
    [
        {
            "value_template": "{{ 'on' }}",
            "turn_off": {"service": "script.fan_off"},
        },
        {
            "value_template": "{{ 'on' }}",
            "turn_on": {"service": "script.fan_on"},
        },
    ],
)
@pytest.mark.usefixtures("setup_fan")
async def test_wrong_template_config(hass: HomeAssistant) -> None:
    """Test: missing 'turn_on' or 'turn_off' will fail."""
    assert hass.states.async_all("fan") == []


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ is_state('input_boolean.state', 'on') }}")]
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_state_template(hass: HomeAssistant) -> None:
    """Test state template."""
    _verify(hass, STATE_OFF, None, None, None, None)

    hass.states.async_set(_STATE_INPUT_BOOLEAN, STATE_ON)
    await hass.async_block_till_done()

    _verify(hass, STATE_ON, None, None, None, None)

    hass.states.async_set(_STATE_INPUT_BOOLEAN, STATE_OFF)
    await hass.async_block_till_done()

    _verify(hass, STATE_OFF, None, None, None, None)


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("state_template", "expected"),
    [
        ("{{ True }}", STATE_ON),
        ("{{ False }}", STATE_OFF),
        ("{{ x - 1 }}", STATE_UNAVAILABLE),
        ("{{ 7.45 }}", STATE_OFF),
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.usefixtures("setup_state_fan")
async def test_state_template_states(hass: HomeAssistant, expected: str) -> None:
    """Test state template."""
    _verify(hass, expected, None, None, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1}}",
            "{% if states.input_boolean.state.state %}/local/switch.png{% endif %}",
            {},
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.MODERN, "picture"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_fan")
async def test_picture_template(hass: HomeAssistant) -> None:
    """Test picture template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("entity_picture") in ("", None)

    hass.states.async_set(_STATE_INPUT_BOOLEAN, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["entity_picture"] == "/local/switch.png"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1}}",
            "{% if states.input_boolean.state.state %}mdi:eye{% endif %}",
            {},
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.MODERN, "icon"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_fan")
async def test_icon_template(hass: HomeAssistant) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("icon") in ("", None)

    hass.states.async_set(_STATE_INPUT_BOOLEAN, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["icon"] == "mdi:eye"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ states('sensor.percentage') }}",
            PERCENTAGE_ACTION,
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "percentage_template"),
        (ConfigurationStyle.MODERN, "percentage"),
    ],
)
@pytest.mark.parametrize(
    ("percent", "expected"),
    [
        ("0", 0),
        ("33", 33),
        ("invalid", 0),
        ("5000", 0),
        ("100", 100),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_fan")
async def test_percentage_template(
    hass: HomeAssistant, percent: str, expected: int, calls: list[ServiceCall]
) -> None:
    """Test templates with fan percentages from other entities."""
    hass.states.async_set("sensor.percentage", percent)
    await hass.async_block_till_done()
    _verify(hass, STATE_ON, expected, None, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ states('sensor.preset_mode') }}",
            {"preset_modes": ["auto", "smart"], **PRESET_MODE_ACTION},
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "preset_mode_template"),
        (ConfigurationStyle.MODERN, "preset_mode"),
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
    hass.states.async_set("sensor.preset_mode", preset_mode)
    await hass.async_block_till_done()
    _verify(hass, STATE_ON, None, None, None, expected)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ is_state('binary_sensor.oscillating', 'on') }}",
            OSCILLATE_ACTION,
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "oscillating_template"),
        (ConfigurationStyle.MODERN, "oscillating"),
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
    hass.states.async_set("binary_sensor.oscillating", oscillating)
    await hass.async_block_till_done()
    _verify(hass, STATE_ON, None, expected, None, None)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ states('sensor.direction') }}",
            DIRECTION_ACTION,
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "direction_template"),
        (ConfigurationStyle.MODERN, "direction"),
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
    hass.states.async_set("sensor.direction", direction)
    await hass.async_block_till_done()
    _verify(hass, STATE_ON, None, None, expected, None)


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "availability_template": (
                    "{{ is_state('availability_boolean.state', 'on') }}"
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
                "availability": ("{{ is_state('availability_boolean.state', 'on') }}"),
                "state": "{{ 'on' }}",
                "oscillating": "{{ 1 == 1 }}",
                "direction": "{{ 'forward' }}",
                "turn_on": {"service": "script.fan_on"},
                "turn_off": {"service": "script.fan_off"},
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_named_fan")
async def test_availability_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability tempalates with values from other entities."""
    for state, test_assert in ((STATE_ON, True), (STATE_OFF, False)):
        hass.states.async_set(_STATE_AVAILABILITY_BOOLEAN, state)
        await hass.async_block_till_done()
        assert (
            hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE
        ) == test_assert


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "fan_config", "states"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'unavailable' }}",
                **OPTIMISTIC_ON_OFF_ACTIONS,
            },
            [STATE_OFF, None, None, None],
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'unavailable' }}",
                **OPTIMISTIC_ON_OFF_ACTIONS,
            },
            [STATE_OFF, None, None, None],
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
            [STATE_OFF, 0, None, None],
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
            [STATE_OFF, 0, None, None],
        ),
    ],
)
@pytest.mark.usefixtures("setup_named_fan")
async def test_template_with_unavailable_entities(hass: HomeAssistant, states) -> None:
    """Test unavailability with value_template."""
    _verify(hass, states[0], states[1], states[2], states[3], None)


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "fan_config"),
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
    ],
)
@pytest.mark.usefixtures("setup_named_fan")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("fan.test_fan").state != STATE_UNAVAILABLE
    assert "TemplateError" in caplog_setup_text
    assert "x" in caplog_setup_text


@pytest.mark.parametrize(("count", "extra_config"), [(1, OPTIMISTIC_ON_OFF_ACTIONS)])
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'off' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'off' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_on_off(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test turn on and turn off."""

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    for expected_calls, (func, action) in enumerate(
        [
            (common.async_turn_on, "turn_on"),
            (common.async_turn_off, "turn_off"),
        ]
    ):
        await func(hass, TEST_ENTITY_ID)

        assert len(calls) == expected_calls + 1
        assert calls[-1].data["action"] == action
        assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize(
    ("count", "extra_config"),
    [
        (
            1,
            {
                **OPTIMISTIC_ON_OFF_ACTIONS,
                **OPTIMISTIC_PRESET_MODE_CONFIG2,
                **OPTIMISTIC_PERCENTAGE_CONFIG,
            },
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'off' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'off' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_on_with_extra_attributes(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test turn on and turn off."""

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, TEST_ENTITY_ID, 100)

    assert len(calls) == 2
    assert calls[-2].data["action"] == "turn_on"
    assert calls[-2].data["caller"] == TEST_ENTITY_ID

    assert calls[-1].data["action"] == "set_percentage"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["percentage"] == 100

    await common.async_turn_off(hass, TEST_ENTITY_ID)

    assert len(calls) == 3
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    await common.async_turn_on(hass, TEST_ENTITY_ID, None, "auto")

    assert len(calls) == 5
    assert calls[-2].data["action"] == "turn_on"
    assert calls[-2].data["caller"] == TEST_ENTITY_ID

    assert calls[-1].data["action"] == "set_preset_mode"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["preset_mode"] == "auto"

    await common.async_turn_off(hass, TEST_ENTITY_ID)

    assert len(calls) == 6
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    await common.async_turn_on(hass, TEST_ENTITY_ID, 50, "high")

    assert len(calls) == 9
    assert calls[-3].data["action"] == "turn_on"
    assert calls[-3].data["caller"] == TEST_ENTITY_ID

    assert calls[-2].data["action"] == "set_preset_mode"
    assert calls[-2].data["caller"] == TEST_ENTITY_ID
    assert calls[-2].data["preset_mode"] == "high"

    assert calls[-1].data["action"] == "set_percentage"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["percentage"] == 50

    await common.async_turn_off(hass, TEST_ENTITY_ID)

    assert len(calls) == 10
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, {**OPTIMISTIC_ON_OFF_ACTIONS, **DIRECTION_ACTION})]
)
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_set_invalid_direction_from_initial_stage(hass: HomeAssistant) -> None:
    """Test set invalid direction when fan is in initial state."""
    await common.async_set_direction(hass, TEST_ENTITY_ID, "invalid")
    _verify(hass, STATE_ON, None, None, None, None)


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, {**OPTIMISTIC_ON_OFF_ACTIONS, **OSCILLATE_ACTION})]
)
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_set_osc(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set oscillating."""
    expected_calls = 0

    await common.async_turn_on(hass, TEST_ENTITY_ID)
    expected_calls += 1
    for state in (True, False):
        await common.async_oscillate(hass, TEST_ENTITY_ID, state)
        _verify(hass, STATE_ON, None, state, None, None)
        expected_calls += 1
        assert len(calls) == expected_calls
        assert calls[-1].data["action"] == "set_oscillating"
        assert calls[-1].data["caller"] == TEST_ENTITY_ID
        assert calls[-1].data["oscillating"] == state


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, {**OPTIMISTIC_ON_OFF_ACTIONS, **DIRECTION_ACTION})]
)
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_set_direction(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set valid direction."""
    expected_calls = 0

    await common.async_turn_on(hass, TEST_ENTITY_ID)
    expected_calls += 1
    for direction in (DIRECTION_FORWARD, DIRECTION_REVERSE):
        await common.async_set_direction(hass, TEST_ENTITY_ID, direction)
        _verify(hass, STATE_ON, None, None, direction, None)
        expected_calls += 1
        assert len(calls) == expected_calls
        assert calls[-1].data["action"] == "set_direction"
        assert calls[-1].data["caller"] == TEST_ENTITY_ID
        assert calls[-1].data["direction"] == direction


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, {**OPTIMISTIC_ON_OFF_ACTIONS, **DIRECTION_ACTION})]
)
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_set_invalid_direction(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set invalid direction when fan has valid direction."""
    expected_calls = 1
    for direction in (DIRECTION_FORWARD, "invalid"):
        await common.async_set_direction(hass, TEST_ENTITY_ID, direction)
        _verify(hass, STATE_ON, None, None, DIRECTION_FORWARD, None)
        assert len(calls) == expected_calls
        assert calls[-1].data["action"] == "set_direction"
        assert calls[-1].data["caller"] == TEST_ENTITY_ID
        assert calls[-1].data["direction"] == DIRECTION_FORWARD


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_PRESET_MODE_CONFIG2)]
)
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_preset_modes(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test preset_modes."""
    expected_calls = 0
    valid_modes = OPTIMISTIC_PRESET_MODE_CONFIG2["preset_modes"]
    for mode in ("auto", "low", "medium", "high", "invalid", "smart"):
        if mode not in valid_modes:
            with pytest.raises(NotValidPresetModeError):
                await common.async_set_preset_mode(hass, TEST_ENTITY_ID, mode)
        else:
            await common.async_set_preset_mode(hass, TEST_ENTITY_ID, mode)
            expected_calls += 1

            assert len(calls) == expected_calls
            assert calls[-1].data["action"] == "set_preset_mode"
            assert calls[-1].data["caller"] == TEST_ENTITY_ID
            assert calls[-1].data["preset_mode"] == mode


@pytest.mark.parametrize(("count", "extra_config"), [(1, OPTIMISTIC_PERCENTAGE_CONFIG)])
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_set_percentage(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set valid speed percentage."""
    expected_calls = 0

    await common.async_turn_on(hass, TEST_ENTITY_ID)
    expected_calls += 1
    for state, value in (
        (STATE_ON, 100),
        (STATE_ON, 66),
        (STATE_ON, 0),
    ):
        await common.async_set_percentage(hass, TEST_ENTITY_ID, value)
        _verify(hass, state, value, None, None, None)
        expected_calls += 1
        assert len(calls) == expected_calls
        assert calls[-1].data["action"] == "set_percentage"
        assert calls[-1].data["caller"] == TEST_ENTITY_ID
        assert calls[-1].data["percentage"] == value

    await common.async_turn_on(hass, TEST_ENTITY_ID, percentage=50)
    _verify(hass, STATE_ON, 50, None, None, None)


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, {"speed_count": 3, **OPTIMISTIC_PERCENTAGE_CONFIG})]
)
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_increase_decrease_speed(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set valid increase and decrease speed."""

    await common.async_turn_on(hass, TEST_ENTITY_ID)
    for func, extra, state, value in (
        (common.async_set_percentage, 100, STATE_ON, 100),
        (common.async_decrease_speed, None, STATE_ON, 66),
        (common.async_decrease_speed, None, STATE_ON, 33),
        (common.async_decrease_speed, None, STATE_ON, 0),
        (common.async_increase_speed, None, STATE_ON, 33),
    ):
        await func(hass, TEST_ENTITY_ID, extra)
        _verify(hass, state, value, None, None, None)


@pytest.mark.parametrize(
    ("count", "fan_config"),
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
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN],
)
@pytest.mark.usefixtures("setup_named_fan")
async def test_optimistic_state(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test a fan without a value_template."""

    await common.async_turn_on(hass, TEST_ENTITY_ID)
    _verify(hass, STATE_ON)

    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    await common.async_turn_off(hass, TEST_ENTITY_ID)
    _verify(hass, STATE_OFF)

    assert len(calls) == 2
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    percent = 100
    await common.async_set_percentage(hass, TEST_ENTITY_ID, percent)
    _verify(hass, STATE_ON, percent)

    assert len(calls) == 3
    assert calls[-1].data["action"] == "set_percentage"
    assert calls[-1].data["percentage"] == 100
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    await common.async_turn_off(hass, TEST_ENTITY_ID)
    _verify(hass, STATE_OFF, percent)

    assert len(calls) == 4
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    preset = "auto"
    await common.async_set_preset_mode(hass, TEST_ENTITY_ID, preset)
    _verify(hass, STATE_ON, percent, None, None, preset)

    assert len(calls) == 5
    assert calls[-1].data["action"] == "set_preset_mode"
    assert calls[-1].data["preset_mode"] == preset
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    await common.async_turn_off(hass, TEST_ENTITY_ID)
    _verify(hass, STATE_OFF, percent, None, None, preset)

    assert len(calls) == 6
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    await common.async_set_direction(hass, TEST_ENTITY_ID, DIRECTION_FORWARD)
    _verify(hass, STATE_OFF, percent, None, DIRECTION_FORWARD, preset)

    assert len(calls) == 7
    assert calls[-1].data["action"] == "set_direction"
    assert calls[-1].data["direction"] == DIRECTION_FORWARD
    assert calls[-1].data["caller"] == TEST_ENTITY_ID

    await common.async_oscillate(hass, TEST_ENTITY_ID, True)
    _verify(hass, STATE_OFF, percent, True, DIRECTION_FORWARD, preset)

    assert len(calls) == 8
    assert calls[-1].data["action"] == "set_oscillating"
    assert calls[-1].data["oscillating"] is True
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
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

    await coro(hass, TEST_ENTITY_ID, value)
    _verify(hass, STATE_ON, **{verify_attr: value})

    assert len(calls) == 1
    assert calls[-1].data["action"] == action
    assert calls[-1].data[attribute] == value
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize(("count", "extra_config"), [(1, OPTIMISTIC_PERCENTAGE_CONFIG)])
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_increase_decrease_speed_default_speed_count(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set valid increase and decrease speed."""
    await common.async_turn_on(hass, TEST_ENTITY_ID)
    for func, extra, state, value in (
        (common.async_set_percentage, 100, STATE_ON, 100),
        (common.async_decrease_speed, None, STATE_ON, 99),
        (common.async_decrease_speed, None, STATE_ON, 98),
        (common.async_decrease_speed, 31, STATE_ON, 67),
        (common.async_decrease_speed, None, STATE_ON, 66),
    ):
        await func(hass, TEST_ENTITY_ID, extra)
        _verify(hass, state, value, None, None, None)


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, {**OPTIMISTIC_ON_OFF_ACTIONS, **OSCILLATE_ACTION})]
)
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_set_invalid_osc_from_initial_state(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set invalid oscillating when fan is in initial state."""
    await common.async_turn_on(hass, TEST_ENTITY_ID)
    with pytest.raises(vol.Invalid):
        await common.async_oscillate(hass, TEST_ENTITY_ID, "invalid")
    _verify(hass, STATE_ON, None, None, None, None)


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, {**OPTIMISTIC_ON_OFF_ACTIONS, **OSCILLATE_ACTION})]
)
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "value_template": "{{ 'on' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "state": "{{ 'on' }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_set_invalid_osc(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set invalid oscillating when fan has valid osc."""
    await common.async_turn_on(hass, TEST_ENTITY_ID)
    await common.async_oscillate(hass, TEST_ENTITY_ID, True)
    _verify(hass, STATE_ON, None, True, None, None)

    await common.async_oscillate(hass, TEST_ENTITY_ID, False)
    _verify(hass, STATE_ON, None, False, None, None)

    with pytest.raises(vol.Invalid):
        await common.async_oscillate(hass, TEST_ENTITY_ID, None)
    _verify(hass, STATE_ON, None, False, None, None)


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("fan_config", "style"),
    [
        (
            {
                "test_template_cover_01": UNIQUE_ID_CONFIG,
                "test_template_cover_02": UNIQUE_ID_CONFIG,
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            [
                {
                    "name": "test_template_cover_01",
                    **UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_cover_02",
                    **UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.MODERN,
        ),
    ],
)
@pytest.mark.usefixtures("setup_fan")
async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option only creates one fan per id."""
    assert len(hass.states.async_all()) == 1


@pytest.mark.parametrize(
    ("count", "extra_config"),
    [(1, {**OPTIMISTIC_ON_OFF_ACTIONS, **OPTIMISTIC_PERCENTAGE_CONFIG})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN],
)
@pytest.mark.parametrize(
    ("fan_config", "percentage_step"),
    [({"speed_count": 0}, 1), ({"speed_count": 100}, 1), ({"speed_count": 3}, 100 / 3)],
)
@pytest.mark.usefixtures("setup_test_fan_with_extra_config")
async def test_speed_percentage_step(hass: HomeAssistant, percentage_step) -> None:
    """Test a fan that implements percentage."""
    assert len(hass.states.async_all()) == 1

    state = hass.states.get(TEST_ENTITY_ID)
    attributes = state.attributes
    assert attributes["percentage_step"] == percentage_step
    assert attributes.get("supported_features") & FanEntityFeature.SET_SPEED


@pytest.mark.parametrize(
    ("count", "fan_config"),
    [(1, {**OPTIMISTIC_ON_OFF_ACTIONS, **OPTIMISTIC_PRESET_MODE_CONFIG2})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN],
)
@pytest.mark.usefixtures("setup_named_fan")
async def test_preset_mode_supported_features(hass: HomeAssistant) -> None:
    """Test a fan that implements preset_mode."""
    assert len(hass.states.async_all()) == 1

    state = hass.states.get(TEST_ENTITY_ID)
    attributes = state.attributes
    assert attributes.get("supported_features") & FanEntityFeature.PRESET_MODE


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "fan_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "turn_on": [],
                "turn_off": [],
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "turn_on": [],
                "turn_off": [],
            },
        ),
    ],
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
async def test_empty_action_config(
    hass: HomeAssistant,
    supported_features: FanEntityFeature,
    setup_test_fan_with_extra_config,
) -> None:
    """Test configuration with empty script."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["supported_features"] == (
        FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON | supported_features
    )


async def test_nested_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a template unique_id propagates to switch unique_ids."""
    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                "template": {
                    "unique_id": "x",
                    "fan": [
                        {
                            **OPTIMISTIC_ON_OFF_ACTIONS,
                            "name": "test_a",
                            "unique_id": "a",
                            "state": "{{ true }}",
                        },
                        {
                            **OPTIMISTIC_ON_OFF_ACTIONS,
                            "name": "test_b",
                            "unique_id": "b",
                            "state": "{{ true }}",
                        },
                    ],
                },
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("fan")) == 2

    entry = entity_registry.async_get("fan.test_a")
    assert entry
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get("fan.test_b")
    assert entry
    assert entry.unique_id == "x-b"
