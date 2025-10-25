"""The tests for the Template vacuum platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import template, vacuum
from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL,
    ATTR_FAN_SPEED,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

from .conftest import ConfigurationStyle, async_get_flow_preview_state

from tests.common import MockConfigEntry, assert_setup_component
from tests.components.vacuum import common
from tests.typing import WebSocketGenerator

TEST_OBJECT_ID = "test_vacuum"
TEST_ENTITY_ID = f"vacuum.{TEST_OBJECT_ID}"

TEST_STATE_SENSOR = "sensor.test_state"
TEST_SPEED_SENSOR = "sensor.test_fan_speed"
TEST_BATTERY_LEVEL_SENSOR = "sensor.test_battery_level"
TEST_AVAILABILITY_ENTITY = "availability_state.state"

TEST_STATE_TRIGGER = {
    "trigger": {
        "trigger": "state",
        "entity_id": [
            TEST_STATE_SENSOR,
            TEST_SPEED_SENSOR,
            TEST_BATTERY_LEVEL_SENSOR,
            TEST_AVAILABILITY_ENTITY,
        ],
    },
    "variables": {"triggering_entity": "{{ trigger.entity_id }}"},
    "action": [
        {"event": "action_event", "event_data": {"what": "{{ triggering_entity }}"}}
    ],
}

START_ACTION = {
    "start": {
        "service": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "action": "start",
        },
    },
}


TEMPLATE_VACUUM_ACTIONS = {
    **START_ACTION,
    "pause": {
        "service": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "action": "pause",
        },
    },
    "stop": {
        "service": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "action": "stop",
        },
    },
    "return_to_base": {
        "service": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "action": "return_to_base",
        },
    },
    "clean_spot": {
        "service": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "action": "clean_spot",
        },
    },
    "locate": {
        "service": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "action": "locate",
        },
    },
    "set_fan_speed": {
        "service": "test.automation",
        "data": {
            "caller": "{{ this.entity_id }}",
            "action": "set_fan_speed",
            "fan_speed": "{{ fan_speed }}",
        },
    },
}

UNIQUE_ID_CONFIG = {"unique_id": "not-so-unique-anymore", **TEMPLATE_VACUUM_ACTIONS}


def _verify(
    hass: HomeAssistant,
    expected_state: str,
    expected_battery_level: int | None = None,
    expected_fan_speed: int | None = None,
) -> None:
    """Verify vacuum's state and speed."""
    state = hass.states.get(TEST_ENTITY_ID)
    attributes = state.attributes
    assert state.state == expected_state
    assert attributes.get(ATTR_BATTERY_LEVEL) == expected_battery_level
    assert attributes.get(ATTR_FAN_SPEED) == expected_fan_speed


async def async_setup_legacy_format(
    hass: HomeAssistant, count: int, vacuum_config: dict[str, Any]
) -> None:
    """Do setup of vacuum integration via new format."""
    config = {"vacuum": {"platform": "template", "vacuums": vacuum_config}}

    with assert_setup_component(count, vacuum.DOMAIN):
        assert await async_setup_component(
            hass,
            vacuum.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_modern_format(
    hass: HomeAssistant, count: int, vacuum_config: dict[str, Any]
) -> None:
    """Do setup of vacuum integration via modern format."""
    config = {"template": {"vacuum": vacuum_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_trigger_format(
    hass: HomeAssistant, count: int, vacuum_config: dict[str, Any]
) -> None:
    """Do setup of vacuum integration via trigger format."""
    config = {"template": {"vacuum": vacuum_config, **TEST_STATE_TRIGGER}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.fixture
async def setup_vacuum(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    vacuum_config: dict[str, Any],
) -> None:
    """Do setup of number integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(hass, count, vacuum_config)
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, vacuum_config)
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(hass, count, vacuum_config)


@pytest.fixture
async def setup_test_vacuum_with_extra_config(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    vacuum_config: dict[str, Any],
    extra_config: dict[str, Any],
) -> None:
    """Do setup of number integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass, count, {TEST_OBJECT_ID: {**vacuum_config, **extra_config}}
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass, count, {"name": TEST_OBJECT_ID, **vacuum_config, **extra_config}
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass, count, {"name": TEST_OBJECT_ID, **vacuum_config, **extra_config}
        )


@pytest.fixture
async def setup_state_vacuum(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of vacuum integration using a state template."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    "value_template": state_template,
                    **TEMPLATE_VACUUM_ACTIONS,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                "state": state_template,
                **TEMPLATE_VACUUM_ACTIONS,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                "state": state_template,
                **TEMPLATE_VACUUM_ACTIONS,
            },
        )


@pytest.fixture
async def setup_base_vacuum(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str | None,
    extra_config: dict,
):
    """Do setup of vacuum integration using a state template."""
    if style == ConfigurationStyle.LEGACY:
        state_config = {"value_template": state_template} if state_template else {}
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **state_config,
                    **extra_config,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        state_config = {"state": state_template} if state_template else {}
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                **state_config,
                **extra_config,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        state_config = {"state": state_template} if state_template else {}
        await async_setup_trigger_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                **state_config,
                **extra_config,
            },
        )


@pytest.fixture
async def setup_single_attribute_state_vacuum(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str | None,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of vacuum integration testing a single attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    if style == ConfigurationStyle.LEGACY:
        state_config = {"value_template": state_template} if state_template else {}
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    **state_config,
                    **TEMPLATE_VACUUM_ACTIONS,
                    **extra,
                    **extra_config,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        state_config = {"state": state_template} if state_template else {}
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                **state_config,
                **TEMPLATE_VACUUM_ACTIONS,
                **extra,
                **extra_config,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        state_config = {"state": state_template} if state_template else {}
        await async_setup_trigger_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                **state_config,
                **TEMPLATE_VACUUM_ACTIONS,
                **extra,
                **extra_config,
            },
        )


@pytest.fixture
async def setup_attributes_state_vacuum(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str | None,
    attributes: dict,
) -> None:
    """Do setup of vacuum integration testing a single attribute."""
    if style == ConfigurationStyle.LEGACY:
        state_config = {"value_template": state_template} if state_template else {}
        await async_setup_legacy_format(
            hass,
            count,
            {
                TEST_OBJECT_ID: {
                    "attribute_templates": attributes,
                    **state_config,
                    **TEMPLATE_VACUUM_ACTIONS,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        state_config = {"state": state_template} if state_template else {}
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                "attributes": attributes,
                **state_config,
                **TEMPLATE_VACUUM_ACTIONS,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        state_config = {"state": state_template} if state_template else {}
        await async_setup_trigger_format(
            hass,
            count,
            {
                "name": TEST_OBJECT_ID,
                "attributes": attributes,
                **state_config,
                **TEMPLATE_VACUUM_ACTIONS,
            },
        )


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "state_template", "extra_config", "parm1", "parm2"),
    [
        (
            ConfigurationStyle.LEGACY,
            None,
            {"start": {"service": "script.vacuum_start"}},
            STATE_UNKNOWN,
            None,
        ),
        (
            ConfigurationStyle.MODERN,
            None,
            {"start": {"service": "script.vacuum_start"}},
            STATE_UNKNOWN,
            None,
        ),
        (
            ConfigurationStyle.TRIGGER,
            None,
            {"start": {"service": "script.vacuum_start"}},
            STATE_UNKNOWN,
            None,
        ),
        (
            ConfigurationStyle.LEGACY,
            "{{ 'cleaning' }}",
            {
                "battery_level_template": "{{ 100 }}",
                "start": {"service": "script.vacuum_start"},
            },
            VacuumActivity.CLEANING,
            100,
        ),
        (
            ConfigurationStyle.MODERN,
            "{{ 'cleaning' }}",
            {
                "battery_level": "{{ 100 }}",
                "start": {"service": "script.vacuum_start"},
            },
            VacuumActivity.CLEANING,
            100,
        ),
        (
            ConfigurationStyle.TRIGGER,
            "{{ 'cleaning' }}",
            {
                "battery_level": "{{ 100 }}",
                "start": {"service": "script.vacuum_start"},
            },
            VacuumActivity.CLEANING,
            100,
        ),
        (
            ConfigurationStyle.LEGACY,
            "{{ 'abc' }}",
            {
                "battery_level_template": "{{ 101 }}",
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNKNOWN,
            None,
        ),
        (
            ConfigurationStyle.MODERN,
            "{{ 'abc' }}",
            {
                "battery_level": "{{ 101 }}",
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNKNOWN,
            None,
        ),
        (
            ConfigurationStyle.TRIGGER,
            "{{ 'abc' }}",
            {
                "battery_level": "{{ 101 }}",
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNKNOWN,
            None,
        ),
        (
            ConfigurationStyle.LEGACY,
            "{{ this_function_does_not_exist() }}",
            {
                "battery_level_template": "{{ this_function_does_not_exist() }}",
                "fan_speed_template": "{{ this_function_does_not_exist() }}",
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNKNOWN,
            None,
        ),
        (
            ConfigurationStyle.MODERN,
            "{{ this_function_does_not_exist() }}",
            {
                "battery_level": "{{ this_function_does_not_exist() }}",
                "fan_speed": "{{ this_function_does_not_exist() }}",
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNKNOWN,
            None,
        ),
        (
            ConfigurationStyle.TRIGGER,
            "{{ this_function_does_not_exist() }}",
            {
                "battery_level": "{{ this_function_does_not_exist() }}",
                "fan_speed": "{{ this_function_does_not_exist() }}",
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNAVAILABLE,
            None,
        ),
    ],
)
@pytest.mark.usefixtures("setup_base_vacuum")
async def test_valid_legacy_configs(hass: HomeAssistant, count, parm1, parm2) -> None:
    """Test: configs."""

    # Ensure trigger entity templates are rendered
    hass.states.async_set(TEST_STATE_SENSOR, None)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("vacuum")) == count
    _verify(hass, parm1, parm2)


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("state_template", "extra_config"),
    [
        ("{{ 'on' }}", {}),
        (None, {"nothingburger": {"service": "script.vacuum_start"}}),
    ],
)
@pytest.mark.usefixtures("setup_base_vacuum")
async def test_invalid_configs(hass: HomeAssistant, count) -> None:
    """Test: configs."""
    assert len(hass.states.async_all("vacuum")) == count


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ states('sensor.test_state') }}", {})],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "battery_level_template"),
        (ConfigurationStyle.MODERN, "battery_level"),
        (ConfigurationStyle.TRIGGER, "battery_level"),
    ],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ '0' }}", 0),
        ("{{ 100 }}", 100),
        ("{{ 101 }}", None),
        ("{{ -1 }}", None),
        ("{{ 'foo' }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_battery_level_template(
    hass: HomeAssistant, expected: int | None
) -> None:
    """Test templates with values from other entities."""
    # Ensure trigger entity templates are rendered
    hass.states.async_set(TEST_STATE_SENSOR, None)
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, expected)


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config", "attribute_template"),
    [(1, "{{ states('sensor.test_state') }}", {}, "{{ 50 }}")],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "battery_level_template"),
        (ConfigurationStyle.MODERN, "battery_level"),
        (ConfigurationStyle.TRIGGER, "battery_level"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_battery_level_template_repair(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test battery_level template raises issue."""
    # Ensure trigger entity templates are rendered
    hass.states.async_set(TEST_STATE_SENSOR, VacuumActivity.DOCKED)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(
        "template", f"deprecated_battery_level_{TEST_ENTITY_ID}"
    )
    assert issue.domain == "template"
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders["entity_name"] == TEST_OBJECT_ID
    assert issue.translation_placeholders["entity_id"] == TEST_ENTITY_ID
    assert "Detected that integration 'template' is setting the" not in caplog.text


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            {
                "fan_speeds": ["low", "medium", "high"],
            },
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "fan_speed_template"),
        (ConfigurationStyle.MODERN, "fan_speed"),
        (ConfigurationStyle.TRIGGER, "fan_speed"),
    ],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ 'low' }}", "low"),
        ("{{ 'medium' }}", "medium"),
        ("{{ 'high' }}", "high"),
        ("{{ 'invalid' }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_fan_speed_template(hass: HomeAssistant, expected: str | None) -> None:
    """Test templates with values from other entities."""
    # Ensure trigger entity templates are rendered
    hass.states.async_set(TEST_STATE_SENSOR, None)
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, None, expected)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config", "attribute"),
    [
        (
            1,
            "{{ 'on' }}",
            "{% if states.sensor.test_state.state %}mdi:check{% endif %}",
            {},
            "icon",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (ConfigurationStyle.MODERN, ""),
        (ConfigurationStyle.TRIGGER, None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_icon_template(hass: HomeAssistant, expected: int) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("icon") == expected

    hass.states.async_set(TEST_STATE_SENSOR, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config", "attribute"),
    [
        (
            1,
            "{{ 'on' }}",
            "{% if states.sensor.test_state.state %}local/vacuum.png{% endif %}",
            {},
            "picture",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (ConfigurationStyle.MODERN, ""),
        (ConfigurationStyle.TRIGGER, None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_picture_template(hass: HomeAssistant, expected: int) -> None:
    """Test picture template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes.get("entity_picture") == expected

    hass.states.async_set(TEST_STATE_SENSOR, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["entity_picture"] == "local/vacuum.png"


@pytest.mark.parametrize("extra_config", [{}])
@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            None,
            "{{ is_state('availability_state.state', 'on') }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""

    # When template returns true..
    hass.states.async_set(TEST_AVAILABILITY_ENTITY, STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get(TEST_ENTITY_ID).state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set(TEST_AVAILABILITY_ENTITY, STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get(TEST_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize("extra_config", [{}])
@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            None,
            "{{ x - 12 }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid availability keeps the device available."""

    # Ensure state change triggers trigger entity.
    hass.states.async_set(TEST_STATE_SENSOR, None)
    await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID) != STATE_UNAVAILABLE
    err = "'x' is undefined"
    assert err in caplog_setup_text or err in caplog.text


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN]
)
@pytest.mark.parametrize(
    ("count", "state_template", "attributes"),
    [
        (
            1,
            "{{ 'cleaning' }}",
            {"test_attribute": "It {{ states.sensor.test_state.state }}."},
        )
    ],
)
@pytest.mark.usefixtures("setup_attributes_state_vacuum")
async def test_attribute_templates(hass: HomeAssistant) -> None:
    """Test attribute_templates template."""
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["test_attribute"] == "It ."

    hass.states.async_set(TEST_STATE_SENSOR, "Works")
    await hass.async_block_till_done()
    await async_update_entity(hass, TEST_ENTITY_ID)
    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["test_attribute"] == "It Works."


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("count", "state_template", "attributes"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            {"test_attribute": "{{ this_function_does_not_exist() }}"},
        )
    ],
)
@pytest.mark.usefixtures("setup_attributes_state_vacuum")
async def test_invalid_attribute_template(
    hass: HomeAssistant, caplog_setup_text, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that errors are logged if rendering template fails."""

    hass.states.async_set(TEST_STATE_SENSOR, "Works")
    await hass.async_block_till_done()

    assert len(hass.states.async_all("vacuum")) == 1
    err = "'this_function_does_not_exist' is undefined"
    assert err in caplog_setup_text or err in caplog.text


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "vacuum_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "test_template_vacuum_01": {
                    "value_template": "{{ true }}",
                    **UNIQUE_ID_CONFIG,
                },
                "test_template_vacuum_02": {
                    "value_template": "{{ false }}",
                    **UNIQUE_ID_CONFIG,
                },
            },
        ),
        (
            ConfigurationStyle.MODERN,
            [
                {
                    "name": "test_template_vacuum_01",
                    "state": "{{ true }}",
                    **UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_vacuum_02",
                    "state": "{{ false }}",
                    **UNIQUE_ID_CONFIG,
                },
            ],
        ),
        (
            ConfigurationStyle.TRIGGER,
            [
                {
                    "name": "test_template_vacuum_01",
                    "state": "{{ true }}",
                    **UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_vacuum_02",
                    "state": "{{ false }}",
                    **UNIQUE_ID_CONFIG,
                },
            ],
        ),
    ],
)
@pytest.mark.usefixtures("setup_vacuum")
async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique_id option only creates one vacuum per id."""
    assert len(hass.states.async_all("vacuum")) == 1


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"), [(1, None, START_ACTION)]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_base_vacuum")
async def test_unused_services(hass: HomeAssistant) -> None:
    """Test calling unused services raises."""
    # Pause vacuum
    with pytest.raises(HomeAssistantError):
        await common.async_pause(hass, TEST_ENTITY_ID)
    await hass.async_block_till_done()

    # Stop vacuum
    with pytest.raises(HomeAssistantError):
        await common.async_stop(hass, TEST_ENTITY_ID)
    await hass.async_block_till_done()

    # Return vacuum to base
    with pytest.raises(HomeAssistantError):
        await common.async_return_to_base(hass, TEST_ENTITY_ID)
    await hass.async_block_till_done()

    # Spot cleaning
    with pytest.raises(HomeAssistantError):
        await common.async_clean_spot(hass, TEST_ENTITY_ID)
    await hass.async_block_till_done()

    # Locate vacuum
    with pytest.raises(HomeAssistantError):
        await common.async_locate(hass, TEST_ENTITY_ID)
    await hass.async_block_till_done()

    # Set fan's speed
    with pytest.raises(HomeAssistantError):
        await common.async_set_fan_speed(hass, "medium", TEST_ENTITY_ID)
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, None)


@pytest.mark.parametrize(
    ("count", "state_template"),
    [(1, "{{ states('sensor.test_state') }}")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "action",
    [
        "start",
        "pause",
        "stop",
        "clean_spot",
        "return_to_base",
        "locate",
    ],
)
@pytest.mark.usefixtures("setup_state_vacuum")
async def test_state_services(
    hass: HomeAssistant, action: str, calls: list[ServiceCall]
) -> None:
    """Test locate service."""

    await hass.services.async_call(
        "vacuum",
        action,
        {"entity_id": TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    # verify
    assert len(calls) == 1
    assert calls[-1].data["action"] == action
    assert calls[-1].data["caller"] == TEST_ENTITY_ID


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            "{{ states('sensor.test_fan_speed') }}",
            {
                "fan_speeds": ["low", "medium", "high"],
            },
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "fan_speed_template"),
        (ConfigurationStyle.MODERN, "fan_speed"),
        (ConfigurationStyle.TRIGGER, "fan_speed"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_set_fan_speed(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set valid fan speed."""

    # Set vacuum's fan speed to high
    await common.async_set_fan_speed(hass, "high", TEST_ENTITY_ID)
    await hass.async_block_till_done()

    # verify
    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_fan_speed"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["fan_speed"] == "high"

    # Set fan's speed to medium
    await common.async_set_fan_speed(hass, "medium", TEST_ENTITY_ID)
    await hass.async_block_till_done()

    # verify
    assert len(calls) == 2
    assert calls[-1].data["action"] == "set_fan_speed"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["fan_speed"] == "medium"


@pytest.mark.parametrize(
    "extra_config",
    [
        {
            "fan_speeds": ["low", "medium", "high"],
        }
    ],
)
@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            "{{ states('sensor.test_fan_speed') }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "fan_speed_template"),
        (ConfigurationStyle.MODERN, "fan_speed"),
        (ConfigurationStyle.TRIGGER, "fan_speed"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_set_invalid_fan_speed(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test set invalid fan speed when fan has valid speed."""

    # Set vacuum's fan speed to high
    await common.async_set_fan_speed(hass, "high", TEST_ENTITY_ID)
    await hass.async_block_till_done()

    # verify
    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_fan_speed"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["fan_speed"] == "high"

    # Set vacuum's fan speed to 'invalid'
    await common.async_set_fan_speed(hass, "invalid", TEST_ENTITY_ID)
    await hass.async_block_till_done()

    # verify fan speed is unchanged
    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_fan_speed"
    assert calls[-1].data["caller"] == TEST_ENTITY_ID
    assert calls[-1].data["fan_speed"] == "high"


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
                    "vacuum": [
                        {
                            **TEMPLATE_VACUUM_ACTIONS,
                            "name": "test_a",
                            "unique_id": "a",
                        },
                        {
                            **TEMPLATE_VACUUM_ACTIONS,
                            "name": "test_b",
                            "unique_id": "b",
                        },
                    ],
                },
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("vacuum")) == 2

    entry = entity_registry.async_get("vacuum.test_a")
    assert entry
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get("vacuum.test_b")
    assert entry
    assert entry.unique_id == "x-b"


@pytest.mark.parametrize(("count", "vacuum_config"), [(1, {"start": []})])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("extra_config", "supported_features"),
    [
        (
            {
                "pause": [],
            },
            VacuumEntityFeature.PAUSE,
        ),
        (
            {
                "stop": [],
            },
            VacuumEntityFeature.STOP,
        ),
        (
            {
                "return_to_base": [],
            },
            VacuumEntityFeature.RETURN_HOME,
        ),
        (
            {
                "clean_spot": [],
            },
            VacuumEntityFeature.CLEAN_SPOT,
        ),
        (
            {
                "locate": [],
            },
            VacuumEntityFeature.LOCATE,
        ),
        (
            {
                "set_fan_speed": [],
            },
            VacuumEntityFeature.FAN_SPEED,
        ),
    ],
)
async def test_empty_action_config(
    hass: HomeAssistant,
    supported_features: VacuumEntityFeature,
    setup_test_vacuum_with_extra_config,
) -> None:
    """Test configuration with empty script."""
    await common.async_start(hass, TEST_ENTITY_ID)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.attributes["supported_features"] == (
        VacuumEntityFeature.STATE | VacuumEntityFeature.START | supported_features
    )


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {"name": TEST_OBJECT_ID, "start": [], **TEMPLATE_VACUUM_ACTIONS},
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("service", "expected"),
    [
        (vacuum.SERVICE_START, VacuumActivity.CLEANING),
        (vacuum.SERVICE_PAUSE, VacuumActivity.PAUSED),
        (vacuum.SERVICE_STOP, VacuumActivity.IDLE),
        (vacuum.SERVICE_RETURN_TO_BASE, VacuumActivity.RETURNING),
        (vacuum.SERVICE_CLEAN_SPOT, VacuumActivity.CLEANING),
    ],
)
@pytest.mark.usefixtures("setup_vacuum")
async def test_assumed_optimistic(
    hass: HomeAssistant,
    service: str,
    expected: VacuumActivity,
    calls: list[ServiceCall],
) -> None:
    """Test assumed optimistic."""

    await hass.services.async_call(
        vacuum.DOMAIN,
        service,
        {"entity_id": TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == expected


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {
                "name": TEST_OBJECT_ID,
                "state": "{{ states('sensor.test_state') }}",
                "start": [],
                **TEMPLATE_VACUUM_ACTIONS,
                "optimistic": True,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("service", "expected"),
    [
        (vacuum.SERVICE_START, VacuumActivity.CLEANING),
        (vacuum.SERVICE_PAUSE, VacuumActivity.PAUSED),
        (vacuum.SERVICE_STOP, VacuumActivity.IDLE),
        (vacuum.SERVICE_RETURN_TO_BASE, VacuumActivity.RETURNING),
        (vacuum.SERVICE_CLEAN_SPOT, VacuumActivity.CLEANING),
    ],
)
@pytest.mark.usefixtures("setup_vacuum")
async def test_optimistic_option(
    hass: HomeAssistant,
    service: str,
    expected: VacuumActivity,
    calls: list[ServiceCall],
) -> None:
    """Test optimistic yaml option."""
    hass.states.async_set(TEST_STATE_SENSOR, VacuumActivity.DOCKED)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == VacuumActivity.DOCKED

    await hass.services.async_call(
        vacuum.DOMAIN,
        service,
        {"entity_id": TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == expected

    hass.states.async_set(TEST_STATE_SENSOR, VacuumActivity.RETURNING)
    await hass.async_block_till_done()

    hass.states.async_set(TEST_STATE_SENSOR, VacuumActivity.DOCKED)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == VacuumActivity.DOCKED


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {
                "name": TEST_OBJECT_ID,
                "state": "{{ states('sensor.test_state') }}",
                "start": [],
                **TEMPLATE_VACUUM_ACTIONS,
                "optimistic": False,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "service",
    [
        vacuum.SERVICE_START,
        vacuum.SERVICE_PAUSE,
        vacuum.SERVICE_STOP,
        vacuum.SERVICE_RETURN_TO_BASE,
        vacuum.SERVICE_CLEAN_SPOT,
    ],
)
@pytest.mark.usefixtures("setup_vacuum")
async def test_not_optimistic(
    hass: HomeAssistant,
    service: str,
    calls: list[ServiceCall],
) -> None:
    """Test optimistic yaml option set to false."""
    await hass.services.async_call(
        vacuum.DOMAIN,
        service,
        {"entity_id": TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_UNKNOWN


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests creating a vacuum from a config entry."""

    hass.states.async_set(
        "sensor.test_sensor",
        "docked",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ states('sensor.test_sensor') }}",
            "start": [],
            "template_type": vacuum.DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("vacuum.my_template")
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
        vacuum.DOMAIN,
        {
            "name": "My template",
            "state": "{{ 'cleaning' }}",
            "start": [],
        },
    )

    assert state["state"] == VacuumActivity.CLEANING
