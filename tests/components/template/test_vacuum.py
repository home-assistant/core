"""The tests for the Template vacuum platform."""

from dataclasses import asdict
from enum import StrEnum
from itertools import chain
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_mock_restore_state_shutdown_restart,
)
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant import config as hass_config
from homeassistant.components import template, vacuum
from homeassistant.components.template.const import (
    VACUUM_DEPRECATED_ATTRIBUTES,
    VACUUM_INCOMPLETE_FAN_SPEED_OPTIONS,
    TemplateService,
)
from homeassistant.components.template.vacuum import (
    CONF_CLEAN_SEGMENTS,
    CONF_SEGMENTS,
    DEPRECATED_HELPER_INCOMPLETE_FAN_SPEED_ISSUE_ID,
)
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    Segment,
    VacuumActivity,
    VacuumEntityCapabilityAttribute,
    VacuumEntityFeature,
    VacuumEntityStateAttribute,
)
from homeassistant.const import (
    CONF_UNIQUE_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml_dict

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    assert_attributes_template,
    assert_invalid_config_entry_actions_do_not_create_entities,
    assert_invalid_yaml_actions_do_not_create_entities,
    assert_state_and_attributes,
    async_get_flow_preview_state,
    async_trigger,
    get_issues_with_prefix,
    make_test_action,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
    setup_mock_template_entity_restore_state,
    setup_restore_template_entity,
)

from tests.components.vacuum import common

TEST_STATE_ENTITY_ID = "sensor.test_state"
TEST_ATTRIBUTE_ENTITY_ID = "sensor.test_attribute"
TEST_AVAILABILITY_ENTITY = "binary_sensor.availability"

TEST_VACUUM = TemplatePlatformSetup(
    vacuum.DOMAIN,
    "test_vacuum",
    make_test_trigger(
        TEST_STATE_ENTITY_ID,
        TEST_ATTRIBUTE_ENTITY_ID,
        TEST_AVAILABILITY_ENTITY,
    ),
)

CLEAN_SPOT_ACTION = make_test_action("clean_spot")
LOCATE_ACTION = make_test_action("locate")
PAUSE_ACTION = make_test_action("pause")
RETURN_TO_BASE_ACTION = make_test_action("return_to_base")
SET_FAN_SPEED_ACTION = make_test_action(
    "set_fan_speed", {"fan_speed": "{{ fan_speed }}"}
)
START_ACTION = make_test_action("start")
STOP_ACTION = make_test_action("stop")
CLEAN_SEGMENTS_ACTION = make_test_action(
    "clean_segments", {"segment_ids": "{{ segment_ids }}"}
)

TEMPLATE_VACUUM_ACTIONS = {
    **START_ACTION,
    **PAUSE_ACTION,
    **STOP_ACTION,
    **RETURN_TO_BASE_ACTION,
    **CLEAN_SPOT_ACTION,
    **LOCATE_ACTION,
    **SET_FAN_SPEED_ACTION,
}


def _verify(
    hass: HomeAssistant,
    expected_state: str,
    expected_fan_speed: str | None = None,
) -> None:
    """Verify vacuum's state and speed."""
    state = hass.states.get(TEST_VACUUM.entity_id)
    attributes = state.attributes
    assert state.state == expected_state
    assert attributes.get(ATTR_FAN_SPEED) == expected_fan_speed


@pytest.fixture
async def setup_vacuum(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    vacuum_config: dict[str, Any],
) -> None:
    """Do setup of number integration."""
    await setup_entity(hass, TEST_VACUUM, style, count, vacuum_config)


@pytest.fixture
async def setup_test_vacuum_with_extra_config(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    vacuum_config: dict[str, Any],
    extra_config: dict[str, Any],
) -> None:
    """Do setup of number integration."""
    await setup_entity(
        hass, TEST_VACUUM, style, count, vacuum_config, extra_config=extra_config
    )


@pytest.fixture
async def setup_state_vacuum(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of vacuum integration using a state template."""
    await setup_entity(
        hass, TEST_VACUUM, style, count, TEMPLATE_VACUUM_ACTIONS, state_template
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
    await setup_entity(hass, TEST_VACUUM, style, count, extra_config, state_template)


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
    config = {attribute: attribute_template} if attribute and attribute_template else {}
    await setup_entity(
        hass,
        TEST_VACUUM,
        style,
        count,
        {**config, **TEMPLATE_VACUUM_ACTIONS},
        state_template,
        extra_config,
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
    await setup_entity(
        hass,
        TEST_VACUUM,
        style,
        count,
        TEMPLATE_VACUUM_ACTIONS,
        state_template,
        attributes=attributes,
    )


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "state_template", "extra_config", "parm1"),
    [
        (
            ConfigurationStyle.MODERN,
            None,
            {"start": {"service": "script.vacuum_start"}},
            STATE_UNKNOWN,
        ),
        (
            ConfigurationStyle.TRIGGER,
            None,
            {"start": {"service": "script.vacuum_start"}},
            STATE_UNKNOWN,
        ),
        (
            ConfigurationStyle.MODERN,
            "{{ 'cleaning' }}",
            {
                "start": {"service": "script.vacuum_start"},
            },
            VacuumActivity.CLEANING,
        ),
        (
            ConfigurationStyle.TRIGGER,
            "{{ 'cleaning' }}",
            {
                "start": {"service": "script.vacuum_start"},
            },
            VacuumActivity.CLEANING,
        ),
        (
            ConfigurationStyle.MODERN,
            "{{ 'abc' }}",
            {
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNKNOWN,
        ),
        (
            ConfigurationStyle.TRIGGER,
            "{{ 'abc' }}",
            {
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNKNOWN,
        ),
        (
            ConfigurationStyle.MODERN,
            "{{ this_function_does_not_exist() }}",
            {
                "fan_speed": "{{ this_function_does_not_exist() }}",
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNAVAILABLE,
        ),
        (
            ConfigurationStyle.TRIGGER,
            "{{ this_function_does_not_exist() }}",
            {
                "fan_speed": "{{ this_function_does_not_exist() }}",
                "start": {"service": "script.vacuum_start"},
            },
            STATE_UNAVAILABLE,
        ),
    ],
)
@pytest.mark.usefixtures("setup_base_vacuum")
async def test_valid_configs(hass: HomeAssistant, count, parm1) -> None:
    """Test: configs."""

    # Ensure trigger entity templates are rendered
    hass.states.async_set(TEST_STATE_ENTITY_ID, None)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("vacuum")) == count
    _verify(hass, parm1)


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    await async_trigger(hass, TEST_STATE_ENTITY_ID)
    _verify(hass, STATE_UNKNOWN, expected)


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
    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.attributes.get("icon") == expected

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_VACUUM.entity_id)
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
    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.attributes.get("entity_picture") == expected

    hass.states.async_set(TEST_STATE_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.attributes["entity_picture"] == "local/vacuum.png"


@pytest.mark.parametrize("extra_config", [{}])
@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            None,
            "{{ is_state('binary_sensor.availability', 'on') }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
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
    assert hass.states.get(TEST_VACUUM.entity_id).state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set(TEST_AVAILABILITY_ENTITY, STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get(TEST_VACUUM.entity_id).state == STATE_UNAVAILABLE


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
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid availability keeps the device available."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID)
    assert hass.states.get(TEST_VACUUM.entity_id) != STATE_UNAVAILABLE
    err = "'x' is undefined"
    assert err in caplog_setup_text or err in caplog.text


@pytest.mark.parametrize("style", [ConfigurationStyle.MODERN])
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
    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.attributes["test_attribute"] == "It ."

    hass.states.async_set(TEST_STATE_ENTITY_ID, "Works")
    await hass.async_block_till_done()
    await async_update_entity(hass, TEST_VACUUM.entity_id)
    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.attributes["test_attribute"] == "It Works."


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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

    hass.states.async_set(TEST_STATE_ENTITY_ID, "Works")
    await hass.async_block_till_done()

    assert len(hass.states.async_all("vacuum")) == 1
    err = "'this_function_does_not_exist' is undefined"
    assert err in caplog_setup_text or err in caplog.text


@pytest.mark.parametrize("config", [TEMPLATE_VACUUM_ACTIONS])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant, style: ConfigurationStyle, config: ConfigType
) -> None:
    """Test unique_id option only creates one vacuum per id."""
    await setup_and_test_unique_id(hass, TEST_VACUUM, style, config)


@pytest.mark.parametrize("config", [TEMPLATE_VACUUM_ACTIONS])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to vacuum unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_VACUUM, style, entity_registry, config
    )


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"), [(1, None, START_ACTION)]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_base_vacuum")
async def test_unused_services(hass: HomeAssistant) -> None:
    """Test calling unused services raises."""
    # Pause vacuum
    with pytest.raises(HomeAssistantError):
        await common.async_pause(hass, TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    # Stop vacuum
    with pytest.raises(HomeAssistantError):
        await common.async_stop(hass, TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    # Return vacuum to base
    with pytest.raises(HomeAssistantError):
        await common.async_return_to_base(hass, TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    # Spot cleaning
    with pytest.raises(HomeAssistantError):
        await common.async_clean_spot(hass, TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    # Locate vacuum
    with pytest.raises(HomeAssistantError):
        await common.async_locate(hass, TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    # Set fan's speed
    with pytest.raises(HomeAssistantError):
        await common.async_set_fan_speed(hass, "medium", TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, None)


@pytest.mark.parametrize(
    ("count", "state_template"),
    [(1, "{{ states('sensor.test_state') }}")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
        {"entity_id": TEST_VACUUM.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # verify
    assert_action(TEST_VACUUM, calls, 1, action)


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template", "extra_config"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            "{{ states('sensor.test_attribute') }}",
            {
                "fan_speeds": ["low", "medium", "high"],
            },
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.MODERN, "fan_speed"),
        (ConfigurationStyle.TRIGGER, "fan_speed"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_state_vacuum")
async def test_set_fan_speed(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test set valid fan speed."""

    # Set vacuum's fan speed to high
    await common.async_set_fan_speed(hass, "high", TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    # verify
    assert_action(TEST_VACUUM, calls, 1, "set_fan_speed", fan_speed="high")

    # Set fan's speed to medium
    await common.async_set_fan_speed(hass, "medium", TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    # verify
    assert_action(TEST_VACUUM, calls, 2, "set_fan_speed", fan_speed="medium")


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
            "{{ states('sensor.test_attribute') }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
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
    await common.async_set_fan_speed(hass, "high", TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    # verify
    assert_action(TEST_VACUUM, calls, 1, "set_fan_speed", fan_speed="high")

    # Set vacuum's fan speed to 'invalid'
    await common.async_set_fan_speed(hass, "invalid", TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    # verify fan speed is unchanged
    assert_action(TEST_VACUUM, calls, 1, "set_fan_speed", fan_speed="high")


@pytest.mark.parametrize(("count", "vacuum_config"), [(1, {"start": []})])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
@pytest.mark.usefixtures("setup_test_vacuum_with_extra_config")
async def test_empty_action_config(
    hass: HomeAssistant,
    supported_features: VacuumEntityFeature,
) -> None:
    """Test configuration with empty script."""
    await common.async_start(hass, TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.attributes["supported_features"] == (
        VacuumEntityFeature.STATE | VacuumEntityFeature.START | supported_features
    )


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {"name": TEST_VACUUM.object_id, "start": [], **TEMPLATE_VACUUM_ACTIONS},
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
        {"entity_id": TEST_VACUUM.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.state == expected


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {
                "name": TEST_VACUUM.object_id,
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
    hass.states.async_set(TEST_STATE_ENTITY_ID, VacuumActivity.DOCKED)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.state == VacuumActivity.DOCKED

    await hass.services.async_call(
        vacuum.DOMAIN,
        service,
        {"entity_id": TEST_VACUUM.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.state == expected

    hass.states.async_set(TEST_STATE_ENTITY_ID, VacuumActivity.RETURNING)
    await hass.async_block_till_done()

    hass.states.async_set(TEST_STATE_ENTITY_ID, VacuumActivity.DOCKED)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.state == VacuumActivity.DOCKED


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {
                "name": TEST_VACUUM.object_id,
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
        {"entity_id": TEST_VACUUM.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {
                "unique_id": TEST_VACUUM.entity_id,
                "start": [],
                **CLEAN_SEGMENTS_ACTION,
                "segments": (
                    "{{ [{'id': '1', 'name': 'Livingroom'},"
                    " {'id': '2', 'name': 'Kitchen'}] }}"
                ),
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_vacuum")
async def test_clean_area(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test clean area passes segment IDs to action."""
    entity_registry.async_update_entity_options(
        TEST_VACUUM.entity_id,
        vacuum.DOMAIN,
        {
            "area_mapping": {"area_1": ["1", "2"]},
            "last_seen_segments": [
                {"id": "1", "name": "Livingroom"},
                {"id": "2", "name": "Kitchen"},
            ],
        },
    )

    await common.async_clean_area(hass, ["area_1"], TEST_VACUUM.entity_id)
    await hass.async_block_till_done()
    assert_action(TEST_VACUUM, calls, 1, "clean_segments", segment_ids=["1", "2"])

    state = hass.states.get(TEST_VACUUM.entity_id)
    assert state is not None
    assert state.attributes["supported_features"] & VacuumEntityFeature.CLEAN_AREA


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {
                "start": [],
                **CLEAN_SEGMENTS_ACTION,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("extra_config", "expected_segments"),
    [
        (
            {
                "unique_id": TEST_VACUUM.entity_id,
                "segments": "{{ ["
                "{'id': '1', 'name': 'Kitchen'}, "
                "{'id': '2', 'name': 'Bedroom', 'group': 'Upstairs'}"
                "] }}",
            },
            [
                Segment(id="1", name="Kitchen"),
                Segment(id="2", name="Bedroom", group="Upstairs"),
            ],
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_vacuum_with_extra_config")
async def test_get_segments(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    expected_segments: list[Segment],
) -> None:
    """Test get_segments returns segments from template."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, VacuumActivity.DOCKED)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": TEST_VACUUM.entity_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "segments": [asdict(segment) for segment in expected_segments]
    }


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {
                "start": [],
                **CLEAN_SEGMENTS_ACTION,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("extra_config", "err_msg"),
    [
        (
            {
                "unique_id": TEST_VACUUM.entity_id,
                "segments": "{{ [ {'id': '1'} ] }}",
            },
            "expected dictionary with keys id, name and optional"
            " group and string values",
        ),
        (
            {
                "unique_id": TEST_VACUUM.entity_id,
                "segments": "{{ [ {'name': 'kitchen'} ] }}",
            },
            "expected dictionary with keys id, name and optional"
            " group and string values",
        ),
        (
            {
                "unique_id": TEST_VACUUM.entity_id,
                "segments": "{{ [ {} ] }}",
            },
            "expected dictionary with keys id, name and optional"
            " group and string values",
        ),
        (
            {
                "unique_id": TEST_VACUUM.entity_id,
                "segments": (
                    "{{ [ {'id': '1', 'name': 'Kitchen', 'extra_key': 'value'} ] }}"
                ),
            },
            "expected dictionary with keys id, name and optional"
            " group and string values",
        ),
        (
            {"unique_id": TEST_VACUUM.entity_id, "segments": "{{ [[]] }}"},
            "expected dictionary with keys id, name and optional"
            " group and string values",
        ),
        (
            {
                "unique_id": TEST_VACUUM.entity_id,
                "segments": "{{ [ {'id': '1', 'name': 'Kitchen'}, [] ] }}",
            },
            "expected dictionary with keys id, name and optional"
            " group and string values",
        ),
    ],
)
@pytest.mark.usefixtures("setup_test_vacuum_with_extra_config")
async def test_invalid_segments(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog_setup_text,
    caplog: pytest.LogCaptureFixture,
    err_msg: str,
) -> None:
    """Test that errors are logged if parsing segment template fails."""
    hass.states.async_set(TEST_STATE_ENTITY_ID, "Works")
    await hass.async_block_till_done()

    assert err_msg in caplog_setup_text or err_msg in caplog.text

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": TEST_VACUUM.entity_id}
    )
    msg = await client.receive_json()
    assert msg["result"] == {"segments": []}


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        (
            1,
            {
                "unique_id": TEST_VACUUM.entity_id,
                "start": [],
                **CLEAN_SEGMENTS_ACTION,
                "segments": (
                    "{{ [ {'id': '1', 'name': 'Kitchen'},"
                    " {'id': '2', 'name':"
                    " states('sensor.test_attribute')}] }}"
                ),
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_vacuum")
async def test_raise_segments_changed_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that issue is raised on segments change."""
    hass.states.async_set(TEST_ATTRIBUTE_ENTITY_ID, "Bedroom")
    await hass.async_block_till_done()

    entity_registry.async_update_entity_options(
        TEST_VACUUM.entity_id,
        vacuum.DOMAIN,
        {
            "last_seen_segments": [
                {"id": "1", "name": "Kitchen"},
                {"id": "2", "name": "Bedroom"},
            ],
        },
    )
    hass.states.async_set(TEST_ATTRIBUTE_ENTITY_ID, "Bathroom")
    await hass.async_block_till_done()

    assert len(issue_registry.issues) != 0


@pytest.mark.parametrize(
    ("vacuum_config", "err_msg"),
    [
        (
            {**START_ACTION},
            f"Options `{CONF_SEGMENTS}` and `{CONF_CLEAN_SEGMENTS}` must both exist",
        ),
    ],
)
@pytest.mark.parametrize(
    ("count", "extra_config"),
    [
        (
            0,
            {
                "segments": "{{ [{'id': '1', 'name': 'Kitchen'}] }}",
            },
        ),
        (
            0,
            {**CLEAN_SEGMENTS_ACTION},
        ),
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_test_vacuum_with_extra_config")
async def test_segments_part_config(
    hass: HomeAssistant,
    caplog_setup_text,
    caplog: pytest.LogCaptureFixture,
    count: int,
    err_msg: str,
) -> None:
    """Test creating vacuum with segments, missing required options."""
    assert len(hass.states.async_all(vacuum.DOMAIN)) == count
    assert err_msg in caplog_setup_text or err_msg in caplog.text


@pytest.mark.parametrize(
    ("vacuum_config"),
    [
        {
            **START_ACTION,
            **CLEAN_SEGMENTS_ACTION,
            "segments": "{{ [{'id': '1', 'name': 'Kitchen'}] }}",
        },
    ],
)
@pytest.mark.parametrize(
    ("count", "extra_config", "err_msg"),
    [
        (
            0,
            {},
            f'key "{CONF_SEGMENTS}" requires key "{CONF_UNIQUE_ID}" to exist',
        ),
        (1, {"unique_id": TEST_VACUUM.entity_id}, ""),
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_test_vacuum_with_extra_config")
async def test_segments_unique_id(
    hass: HomeAssistant,
    caplog_setup_text,
    caplog: pytest.LogCaptureFixture,
    count: int,
    err_msg: str,
) -> None:
    """Test creating vacuum with segments, missing required options."""
    assert len(hass.states.async_all(vacuum.DOMAIN)) == count
    assert err_msg in caplog_setup_text or err_msg in caplog.text


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


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    (
        "saved_state",
        "saved_extra_data",
        "initial_state",
        "initial_attributes",
    ),
    [
        (
            "some_value",
            {
                "activity": VacuumActivity.DOCKED,
                "fan_speed": "high",
            },
            VacuumActivity.DOCKED,
            {
                "fan_speed": "high",
            },
        ),
        (
            "some_value",
            {
                "activity": "do",
            },
            STATE_UNKNOWN,
            {
                "fan_speed": None,
            },
        ),
        (
            "some_value",
            {
                "activity": VacuumActivity.DOCKED,
            },
            STATE_UNKNOWN,
            {
                "fan_speed": None,
            },
        ),
        (
            "some_value",
            {
                "fan_speed": "high",
            },
            STATE_UNKNOWN,
            {
                "fan_speed": None,
            },
        ),
        (
            STATE_UNAVAILABLE,
            {
                "activity": VacuumActivity.DOCKED,
                "fan_speed": "high",
            },
            STATE_UNKNOWN,
            {
                "fan_speed": None,
            },
        ),
        (
            STATE_UNKNOWN,
            {
                "activity": VacuumActivity.DOCKED,
                "fan_speed": "high",
            },
            STATE_UNKNOWN,
            {
                "fan_speed": None,
            },
        ),
    ],
)
async def test_restore_state(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    saved_state: str,
    saved_extra_data: dict | None,
    initial_state: str,
    initial_attributes: ConfigType,
) -> None:
    """Test restoring trigger template vacuum."""

    setup_mock_template_entity_restore_state(
        hass,
        TEST_VACUUM,
        saved_state,
        saved_extra_data=saved_extra_data,
    )

    await setup_restore_template_entity(
        hass,
        TEST_VACUUM,
        style,
        {
            "state": "{{ state_attr('sensor.test_state', 'activity') }}",
            "start": [],
            "fan_speed": "{{ state_attr('sensor.test_state', 'fan_speed') }}",
            "fan_speeds": ["low", "high"],
            "set_fan_speed": [],
        },
        "state_attr('sensor.test_state', 'activity') == 'cleaning'",
    )

    assert_state_and_attributes(
        hass,
        TEST_VACUUM,
        initial_state,
        initial_attributes,
    )

    await async_trigger(
        hass,
        "sensor.test_state",
        "anything",
        {"activity": VacuumActivity.CLEANING, "fan_speed": "low"},
    )

    assert_state_and_attributes(
        hass,
        TEST_VACUUM,
        VacuumActivity.CLEANING,
        {
            "fan_speed": "low",
        },
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_saving_state(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    hass_storage: dict[str, Any],
) -> None:
    """Test restore saved state."""

    await setup_entity(
        hass,
        TEST_VACUUM,
        style,
        1,
        config={
            "state": "{{ state_attr('sensor.test_state', 'activity') }}",
            "start": [],
            "fan_speed": "{{ state_attr('sensor.test_state', 'fan_speed') }}",
            "fan_speeds": ["low", "high"],
            "set_fan_speed": [],
        },
    )

    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "anything",
        {"activity": VacuumActivity.DOCKED, "fan_speed": "high"},
    )

    assert_state_and_attributes(
        hass,
        TEST_VACUUM,
        VacuumActivity.DOCKED,
        {
            "fan_speed": "high",
        },
    )

    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == TEST_VACUUM.entity_id

    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == {
        "activity": "docked",
        "fan_speed": "high",
    }


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("action", "config"),
    [
        (
            "clean_segments",
            {
                "segments": "{{ [{'id': '1', 'name': 'Kitchen'}] }}",
                **START_ACTION,
                "unique_id": "5adfasdffsfsdafad",
            },
        ),
        ("clean_spot", START_ACTION),
        ("locate", START_ACTION),
        ("pause", START_ACTION),
        ("return_to_base", START_ACTION),
        ("set_fan_speed", START_ACTION),
        ("start", {}),
        ("stop", START_ACTION),
    ],
)
async def test_invalid_yaml_actions_do_not_create_entities(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    action: str,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid yaml actions do not create entities."""
    await assert_invalid_yaml_actions_do_not_create_entities(
        hass, TEST_VACUUM, style, config, action, caplog
    )


@pytest.mark.parametrize(
    ("action", "config"),
    [
        (
            "clean_segments",
            {
                "segments": "{{ [{'id': '1', 'name': 'Kitchen'}] }}",
                **START_ACTION,
            },
        ),
        ("clean_spot", START_ACTION),
        ("locate", START_ACTION),
        ("pause", START_ACTION),
        ("return_to_base", START_ACTION),
        ("set_fan_speed", START_ACTION),
        ("start", {}),
        ("stop", START_ACTION),
    ],
)
async def test_invalid_config_entry_actions_do_not_create_entities(
    hass: HomeAssistant,
    action: str,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid config entry actions do not create entities."""
    await assert_invalid_config_entry_actions_do_not_create_entities(
        hass, TEST_VACUUM, config, action, caplog
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_attributes_template(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes as a single template."""
    await assert_attributes_template(
        hass,
        TEST_VACUUM,
        style,
        {
            "start": [],
        },
        caplog,
    )


@pytest.mark.parametrize(
    "attribute",
    list(chain(VacuumEntityCapabilityAttribute, VacuumEntityStateAttribute)),
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_attributes_template_with_blocked_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute: StrEnum,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test blocked attributes for a single attributes template."""
    await setup_entity(
        hass,
        TEST_VACUUM,
        style,
        1,
        {
            "start": [],
            "attributes": f"{{{{ dict({attribute}='does not matter') }}}}",
        },
    )

    await async_trigger(hass, "sensor.test_extra_attributes", "anything")

    error = f"Unsupported attribute(s) found for {TEST_VACUUM.entity_id}: {attribute}"
    assert error in caplog.text


def get_incomplete_fan_speed_options_issues(
    issue_registry: ir.IssueRegistry,
) -> list[ir.IssueEntry]:
    """Return the incomplete vacuum fan speed options issues."""
    return get_issues_with_prefix(
        issue_registry, VACUUM_INCOMPLETE_FAN_SPEED_OPTIONS.translation_key
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("config", "options"),
    [
        pytest.param(
            {"fan_speed": "{{ 'high' }}"},
            "- `fan_speed` requires `fan_speeds` and `set_fan_speed`",
            id="fan_speed_only",
        ),
        pytest.param(
            {"fan_speed": "{{ 'high' }}", "fan_speeds": ["high"]},
            "- `fan_speed` requires `fan_speeds` and `set_fan_speed`\n"
            "- `fan_speeds` requires `set_fan_speed`",
            id="fan_speed_without_action",
        ),
        pytest.param(
            {"fan_speeds": ["high"]},
            "- `fan_speeds` requires `set_fan_speed`",
            id="list_only",
        ),
        pytest.param(
            SET_FAN_SPEED_ACTION,
            "- `set_fan_speed` requires `fan_speeds`",
            id="action_only",
        ),
        pytest.param(
            {**SET_FAN_SPEED_ACTION, "fan_speeds": []},
            "- `set_fan_speed` requires `fan_speeds`",
            id="action_with_empty_list",
        ),
    ],
)
async def test_incomplete_fan_speed_options_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    style: ConfigurationStyle,
    config: ConfigType,
    options: str,
) -> None:
    """Test a repair issue is created for partially set fan speed options."""
    await setup_entity(
        hass, TEST_VACUUM, style, 1, {**START_ACTION, **config}, "{{ 'docked' }}"
    )

    issues = get_incomplete_fan_speed_options_issues(issue_registry)
    assert len(issues) == 1
    assert issues[0].breaks_in_ha_version == "2027.6.0"
    assert issues[0].is_fixable is False
    assert issues[0].severity == ir.IssueSeverity.WARNING
    assert issues[0].learn_more_url == (
        "https://www.home-assistant.io/integrations/template/#vacuum"
    )
    assert (
        issues[0].translation_key == VACUUM_INCOMPLETE_FAN_SPEED_OPTIONS.translation_key
    )
    assert issues[0].translation_placeholders == {
        "identifier": f"name: {TEST_VACUUM.object_id}",
        "options": options,
    }


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "config",
    [
        pytest.param({}, id="none"),
        pytest.param(
            {"fan_speeds": ["high"], **SET_FAN_SPEED_ACTION}, id="without_fan_speed"
        ),
        pytest.param(
            {
                "fan_speed": "{{ 'high' }}",
                "fan_speeds": ["high"],
                **SET_FAN_SPEED_ACTION,
            },
            id="all",
        ),
    ],
)
async def test_no_incomplete_fan_speed_options_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    style: ConfigurationStyle,
    config: ConfigType,
) -> None:
    """Test no repair issue is created for complete fan speed options."""
    await setup_entity(
        hass, TEST_VACUUM, style, 1, {**START_ACTION, **config}, "{{ 'docked' }}"
    )

    assert get_incomplete_fan_speed_options_issues(issue_registry) == []


INCOMPLETE_FAN_SPEED_YAML = """\
template:
  - vacuum:
      - name: Test
        start: []
        set_fan_speed:
          - variables:
              speed: "{{ fan_speed }}"
"""


async def _async_reload_yaml(hass: HomeAssistant, yaml_path: Path, yaml: str) -> None:
    """Write configuration.yaml and reload the template entities from it."""
    await hass.async_add_executor_job(yaml_path.write_text, yaml)
    with patch.object(hass_config, "YAML_CONFIG_FILE", str(yaml_path)):
        await hass.services.async_call(
            template.DOMAIN, TemplateService.RELOAD, blocking=True
        )
    await hass.async_block_till_done()


async def test_incomplete_fan_speed_options_issue_file_and_line(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, tmp_path: Path
) -> None:
    """Test the repair lists file and line, and is removed after a fix."""
    hass.config.config_dir = str(tmp_path)
    yaml_path = tmp_path / "configuration.yaml"
    await hass.async_add_executor_job(yaml_path.write_text, INCOMPLETE_FAN_SPEED_YAML)
    config = await hass.async_add_executor_job(load_yaml_dict, yaml_path)
    assert await async_setup_component(hass, template.DOMAIN, config)
    await hass.async_block_till_done()

    issues = get_incomplete_fan_speed_options_issues(issue_registry)
    assert len(issues) == 1
    assert issues[0].translation_placeholders == {
        "identifier": "name: Test",
        "options": "- `configuration.yaml:5`: `set_fan_speed` requires `fan_speeds`",
    }

    # An ignored repair stays ignored while the configuration is unchanged
    ir.async_ignore_issue(hass, template.DOMAIN, issues[0].issue_id, True)
    await _async_reload_yaml(hass, yaml_path, INCOMPLETE_FAN_SPEED_YAML)
    issue = issue_registry.async_get_issue(template.DOMAIN, issues[0].issue_id)
    assert issue is not None
    assert issue.dismissed_version is not None

    await _async_reload_yaml(
        hass, yaml_path, INCOMPLETE_FAN_SPEED_YAML + "        fan_speeds: [high]\n"
    )
    assert get_incomplete_fan_speed_options_issues(issue_registry) == []


async def test_nested_and_top_level_option_locations(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, tmp_path: Path
) -> None:
    """Test an attribute and an option with the same name keep their own line."""
    hass.config.config_dir = str(tmp_path)
    yaml_path = tmp_path / "configuration.yaml"
    await hass.async_add_executor_job(
        yaml_path.write_text,
        """\
template:
  - vacuum:
      - name: Test
        start: []
        fan_speed: "{{ 'high' }}"
        attributes:
          fan_speed: "{{ 'high' }}"
""",
    )
    config = await hass.async_add_executor_job(load_yaml_dict, yaml_path)
    assert await async_setup_component(hass, template.DOMAIN, config)
    await hass.async_block_till_done()

    issues = get_incomplete_fan_speed_options_issues(issue_registry)
    assert len(issues) == 1
    assert issues[0].translation_placeholders == {
        "identifier": "name: Test",
        "options": (
            "- `configuration.yaml:5`: `fan_speed` requires `fan_speeds`"
            " and `set_fan_speed`"
        ),
    }
    issues = get_deprecated_attributes_issues(issue_registry)
    assert len(issues) == 1
    assert issues[0].translation_placeholders == {
        "identifier": "name: Test",
        "options": "- `configuration.yaml:7`: `attributes: fan_speed` → `fan_speed`",
    }


async def test_incomplete_fan_speed_options_issue_blueprint(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test all instances of a vacuum blueprint share one repair."""
    assert await async_setup_component(
        hass,
        template.DOMAIN,
        {
            template.DOMAIN: [
                {
                    "use_blueprint": {
                        "path": "test_vacuum_incomplete_fan_speed.yaml",
                        "input": {"sensor": sensor, "fan_speeds": fan_speeds},
                    },
                    "name": name,
                }
                # The deprecated options differ per instance
                for sensor, fan_speeds, name in (
                    ("sensor.first", [], "First"),
                    ("sensor.second", ["high"], "Second"),
                )
            ]
        },
    )
    await hass.async_block_till_done()

    issues = get_incomplete_fan_speed_options_issues(issue_registry)
    assert len(issues) == 1
    assert (
        issues[0].translation_key
        == VACUUM_INCOMPLETE_FAN_SPEED_OPTIONS.blueprint_translation_key
    )
    assert issues[0].translation_placeholders == {
        "blueprint": "test_vacuum_incomplete_fan_speed.yaml",
        "options": (
            "- `blueprints/template/test_vacuum_incomplete_fan_speed.yaml:23`: "
            "`fan_speed` requires `fan_speeds` and `set_fan_speed`\n"
            "- `blueprints/template/test_vacuum_incomplete_fan_speed.yaml:24`: "
            "`fan_speeds` requires `set_fan_speed`"
        ),
    }


async def _async_setup_vacuum_config_entry(
    hass: HomeAssistant, options: dict[str, Any]
) -> MockConfigEntry:
    """Set up a template vacuum helper with the given options."""
    config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ 'docked' }}",
            "start": [],
            "template_type": vacuum.DOMAIN,
            **options,
        },
        title="My template",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.mark.parametrize(
    ("options", "expected_options"),
    [
        pytest.param(
            {"set_fan_speed": []},
            "- `set_fan_speed` requires `fan_speeds`",
            id="action_only",
        ),
        pytest.param(
            {"set_fan_speed": [], "fan_speeds": []},
            "- `set_fan_speed` requires `fan_speeds`",
            id="empty_list",
        ),
        pytest.param(
            {"fan_speed": "{{ 'high' }}"},
            "- `fan_speed` requires `fan_speeds` and `set_fan_speed`",
            id="fan_speed_only",
        ),
    ],
)
async def test_incomplete_fan_speed_config_entry_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    options: dict[str, Any],
    expected_options: str,
) -> None:
    """Test a repair issue is tied to a helper with incomplete fan speed options."""
    config_entry = await _async_setup_vacuum_config_entry(hass, options)
    issue_id = (
        f"{DEPRECATED_HELPER_INCOMPLETE_FAN_SPEED_ISSUE_ID}_{config_entry.entry_id}"
    )
    issue = issue_registry.async_get_issue(template.DOMAIN, issue_id)
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.config_entry_id == config_entry.entry_id
    assert issue.translation_key == DEPRECATED_HELPER_INCOMPLETE_FAN_SPEED_ISSUE_ID
    assert issue.translation_placeholders == {
        "name": "My template",
        "breaks_in_ha_version": "2027.6.0",
        "options": expected_options,
    }
    # The YAML repairs don't remove the repairs of helpers
    assert get_incomplete_fan_speed_options_issues(issue_registry) == []

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            **config_entry.options,
            "fan_speeds": ["high"],
            "set_fan_speed": [],
        },
    )
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(template.DOMAIN, issue_id) is None


async def test_incomplete_fan_speed_config_entry_removed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the repair issue is removed with the helper."""
    config_entry = await _async_setup_vacuum_config_entry(hass, {"set_fan_speed": []})
    issue_id = (
        f"{DEPRECATED_HELPER_INCOMPLETE_FAN_SPEED_ISSUE_ID}_{config_entry.entry_id}"
    )
    assert issue_registry.async_get_issue(template.DOMAIN, issue_id) is not None

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(template.DOMAIN, issue_id) is None


async def test_no_incomplete_fan_speed_config_entry_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test no repair issue is created for a helper with complete fan speeds."""
    config_entry = await _async_setup_vacuum_config_entry(
        hass, {"fan_speeds": ["high"], "set_fan_speed": []}
    )
    assert (
        issue_registry.async_get_issue(
            template.DOMAIN,
            f"{DEPRECATED_HELPER_INCOMPLETE_FAN_SPEED_ISSUE_ID}_{config_entry.entry_id}",
        )
        is None
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_optimistic_fan_speed(
    hass: HomeAssistant, style: ConfigurationStyle, calls: list[ServiceCall]
) -> None:
    """Test the fan speed is set optimistically without a fan speed template."""
    await setup_entity(
        hass,
        TEST_VACUUM,
        style,
        1,
        {
            **START_ACTION,
            **SET_FAN_SPEED_ACTION,
            "fan_speeds": ["low", "high"],
        },
        "{{ 'docked' }}",
    )

    await common.async_set_fan_speed(hass, "high", TEST_VACUUM.entity_id)
    await hass.async_block_till_done()

    assert_action(TEST_VACUUM, calls, 1, "set_fan_speed", fan_speed="high")
    assert hass.states.get(TEST_VACUUM.entity_id).attributes[ATTR_FAN_SPEED] == "high"


def get_deprecated_attributes_issues(
    issue_registry: ir.IssueRegistry,
) -> list[ir.IssueEntry]:
    """Return the deprecated attributes issues."""
    return get_issues_with_prefix(
        issue_registry, VACUUM_DEPRECATED_ATTRIBUTES.translation_key
    )


@pytest.mark.parametrize(
    ("count", "vacuum_config", "options"),
    [
        pytest.param(
            1,
            {**START_ACTION, "attributes": {"fan_speed": "{{ 'low' }}"}},
            "- `attributes: fan_speed` → `fan_speed`",
            id="fan_speed",
        ),
        pytest.param(
            1,
            {**START_ACTION, "attributes": {"fan_speed_list": "{{ ['low'] }}"}},
            "- `attributes: fan_speed_list` → `fan_speeds`",
            id="fan_speed_list",
        ),
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_vacuum")
async def test_deprecated_attributes_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, options: str
) -> None:
    """Test a repair issue is created for attributes that have a dedicated option."""
    issues = get_deprecated_attributes_issues(issue_registry)
    assert len(issues) == 1
    assert issues[0].breaks_in_ha_version == "2027.6.0"
    assert issues[0].is_fixable is False
    assert issues[0].severity == ir.IssueSeverity.WARNING
    assert issues[0].learn_more_url == (
        "https://www.home-assistant.io/integrations/template/#vacuum"
    )
    assert issues[0].translation_key == VACUUM_DEPRECATED_ATTRIBUTES.translation_key
    assert issues[0].translation_placeholders == {
        "identifier": f"name: {TEST_VACUUM.object_id}",
        "options": options,
    }


@pytest.mark.parametrize(
    ("count", "vacuum_config"),
    [
        pytest.param(
            1,
            {**START_ACTION, "fan_speeds": ["low"], "attributes": {"other": "{{ 1 }}"}},
            id="dedicated_option",
        ),
        pytest.param(
            1,
            {**START_ACTION, "attributes": "{{ {'fan_speed': 'low'} }}"},
            id="attributes_template",
        ),
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.usefixtures("setup_vacuum")
async def test_no_deprecated_attributes_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test no repair issue is created for dedicated options or allowed attributes."""
    assert get_deprecated_attributes_issues(issue_registry) == []
