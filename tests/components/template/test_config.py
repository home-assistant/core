"""Test Template config."""

from pathlib import Path
from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.common import (
    assert_platform_setup_creates_issue,
    assert_setup_component,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant import config as hass_config
from homeassistant.components.template import DOMAIN
from homeassistant.components.template.config import (
    CONFIG_SECTION_SCHEMA,
    _merge_deprecated_options,
    async_validate_config,
    async_validate_config_section,
)
from homeassistant.components.template.const import (
    PLATFORMS,
    WEATHER_DEPRECATED_OPTIONS,
    DeprecatedTemplateOptions,
    TemplateService,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.discovery import Platform
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml_dict

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    async_trigger,
    get_issues_with_prefix,
    make_mock_device_actions,
    make_test_trigger,
    setup_entity,
    setup_mock_devices,
)


@pytest.mark.parametrize(
    "platform_domain",
    [platform for platform in PLATFORMS if platform != Platform.DEVICE_TRACKER],
)
async def test_platform_config_creates_issue(
    hass: HomeAssistant,
    platform_domain: str,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid platform config creates issue and logs a warning."""
    await assert_platform_setup_creates_issue(
        hass,
        platform_domain,
        DOMAIN,
        issue_registry,
        caplog,
    )


async def test_platform_device_tracker_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid platform config creates issue and logs a warning."""
    caplog.clear()
    integration_domain = DOMAIN
    platform_domain = Platform.DEVICE_TRACKER
    with assert_setup_component(1, platform_domain):
        assert await async_setup_component(
            hass,
            platform_domain,
            {platform_domain: {"platform": integration_domain}},
        )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all(platform_domain)) == 0
    assert (
        f"The {integration_domain} platform for the {platform_domain} integration does not support platform"
        " setup, please remove it from your config" in caplog.text
    )

    issue = issue_registry.async_get_issue(
        "homeassistant",
        f"platform_integration_no_support_{platform_domain}_{integration_domain}",
    )

    assert issue
    assert issue.issue_domain == integration_domain
    assert issue.learn_more_url is None
    assert issue.translation_key == "platform_setup_not_supported"
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {
        "platform_domain": platform_domain,
        "integration_domain": integration_domain,
        "platform_key": f"platform: {integration_domain}",
        "yaml_example": f"```yaml\n{platform_domain}:\n  - platform: {integration_domain}\n```",
    }


@pytest.mark.parametrize(
    "config",
    [
        {
            "trigger": {"trigger": "event", "event_type": "my_event"},
            "button": {
                "press": {
                    "service": "test.automation",
                    "data_template": {"caller": "{{ this.entity_id }}"},
                },
                "device_class": "restart",
                "unique_id": "test",
                "name": "test",
                "icon": "mdi:test",
            },
        },
        {
            "trigger": {"trigger": "event", "event_type": "my_event"},
            "action": {
                "service": "test.automation",
                "data_template": {"caller": "{{ this.entity_id }}"},
            },
            "button": {
                "press": {
                    "service": "test.automation",
                    "data_template": {"caller": "{{ this.entity_id }}"},
                },
                "device_class": "restart",
                "unique_id": "test",
                "name": "test",
                "icon": "mdi:test",
            },
        },
        {
            "trigger": {"trigger": "event", "event_type": "my_event"},
            "trigger_variables": {"a": 1},
            "button": {
                "press": {"action": "test.automation"},
                "name": "test",
            },
        },
        {
            "trigger_variables": {"a": 1},
            "button": {
                "press": {"action": "test.automation"},
                "name": "test",
            },
        },
        {
            "trigger_variables": {"a": 1},
            "sensor": {"name": "test", "state": "{{ 1 }}"},
        },
    ],
)
async def test_invalid_schema(hass: HomeAssistant, config: dict) -> None:
    """Test invalid config schemas."""
    with pytest.raises(probatio.Invalid):
        CONFIG_SECTION_SCHEMA(config)


async def test_valid_default_entity_id(hass: HomeAssistant) -> None:
    """Test valid default_entity_id schemas."""
    config = {
        "button": {
            "press": [],
            "default_entity_id": "button.test",
        },
    }
    assert CONFIG_SECTION_SCHEMA(config) == {
        "button": [
            {
                "press": [],
                "name": Template("Template Button", hass),
                "default_entity_id": "button.test",
            }
        ]
    }


@pytest.mark.parametrize(
    "default_entity_id",
    [
        "foo",
        "{{ 'my_template' }}",
        "SJLIVan as dfkaj;heafha faass00",
        48,
        None,
        "bttn.test",
    ],
)
async def test_invalid_default_entity_id(
    hass: HomeAssistant, default_entity_id: dict
) -> None:
    """Test invalid default_entity_id schemas."""
    config = {
        "button": {
            "press": [],
            "default_entity_id": default_entity_id,
        },
    }
    with pytest.raises(probatio.Invalid):
        CONFIG_SECTION_SCHEMA(config)


@pytest.mark.parametrize(
    ("config", "expected_error"),
    [
        (
            {
                "trigger": {"trigger": "event", "event_type": "my_event"},
                "binary_sensor": {
                    "state": "{{ states('binary_sensor.test') }}",
                    "unique_id": "test",
                    "name": "test",
                    "auto_off": "00:00:01",
                },
            },
            None,
        ),
        (
            {
                "binary_sensor": {
                    "state": "{{ states('binary_sensor.test') }}",
                    "name": "test",
                },
            },
            None,
        ),
        (
            {
                "binary_sensor": {
                    "state": "{{ states('binary_sensor.test') }}",
                    "auto_off": "00:00:01",
                },
            },
            "The auto_off option for template binary sensor:"
            " name: Template Binary Sensor",
        ),
        (
            {
                "binary_sensor": {
                    "state": "{{ states('binary_sensor.test') }}",
                    "name": "test",
                    "auto_off": "00:00:01",
                },
            },
            "The auto_off option for template binary sensor: name: test",
        ),
        (
            {
                "binary_sensor": {
                    "state": "{{ states('binary_sensor.test') }}",
                    "unique_id": "test_unique_id",
                    "auto_off": "00:00:01",
                },
            },
            "The auto_off option for template binary sensor: unique_id: test_unique_id",
        ),
        (
            {
                "binary_sensor": {
                    "state": "{{ states('binary_sensor.test') }}",
                    "name": "test",
                    "unique_id": "test_unique_id",
                    "auto_off": "00:00:01",
                },
            },
            "The auto_off option for template binary sensor: name: test",
        ),
        (
            {
                "binary_sensor": {
                    "state": "{{ states('binary_sensor.test') }}",
                    "default_entity_id": "binary_sensor.test_entity_id",
                    "auto_off": "00:00:01",
                },
            },
            "The auto_off option for template binary sensor:"
            " default_entity_id: binary_sensor.test_entity_id",
        ),
        (
            {
                "binary_sensor": {
                    "state": "{{ states('binary_sensor.test') }}",
                    "name": "test",
                    "unique_id": "test_unique_id",
                    "default_entity_id": "binary_sensor.test_entity_id",
                    "auto_off": "00:00:01",
                },
            },
            "The auto_off option for template binary sensor: name: test",
        ),
        (
            {
                "binary_sensor": {
                    "state": "{{ states('binary_sensor.test') }}",
                    "unique_id": "test_unique_id",
                    "default_entity_id": "binary_sensor.test_entity_id",
                    "auto_off": "00:00:01",
                },
            },
            "The auto_off option for template binary sensor:"
            " default_entity_id: binary_sensor.test_entity_id",
        ),
    ],
)
async def test_invalid_binary_sensor_schema_with_auto_off(
    hass: HomeAssistant,
    config: dict,
    expected_error: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid config schemas create issue and log warning."""

    await async_setup_component(hass, DOMAIN, {"template": [config]})

    assert (
        expected_error is None and "ERROR" not in caplog.text
    ) or expected_error in caplog.text


# Button is omitted because it does not support triggers
TRIGGER_PLATFORM_CONFIGURATIONS = [
    (
        Platform.ALARM_CONTROL_PANEL,
        {
            "state": "{{ 'disarmed' }}",
        },
    ),
    (
        Platform.BINARY_SENSOR,
        {
            "state": "{{ 'on' }}",
        },
    ),
    (
        Platform.COVER,
        {
            "state": "{{ 'open' }}",
            "open_cover": [],
            "close_cover": [],
        },
    ),
    (
        Platform.DEVICE_TRACKER,
        {
            "in_zones": "{{ ['zone.home'] }}",
        },
    ),
    (
        Platform.EVENT,
        {
            "event_type": "{{ 'single' }}",
            "event_types": "{{ ['single'] }}",
        },
    ),
    (
        Platform.FAN,
        {
            "state": "{{ 'on' }}",
            "turn_on": [],
            "turn_off": [],
        },
    ),
    (
        Platform.IMAGE,
        {
            "url": "{{ 'http://www.test.com' }}",
        },
    ),
    (
        Platform.LIGHT,
        {
            "state": "{{ 'on' }}",
            "turn_on": [],
            "turn_off": [],
        },
    ),
    (
        Platform.LOCK,
        {
            "state": "{{ 'on' }}",
            "lock": [],
            "unlock": [],
        },
    ),
    (
        Platform.NUMBER,
        {
            "state": "{{ 4 }}",
            "min": "0",
            "max": "100",
            "step": "0.1",
            "unit_of_measurement": "cm",
            "set_value": [],
        },
    ),
    (
        Platform.SELECT,
        {
            "state": "{{ 'on' }}",
            "options": "{{ ['off', 'on', 'auto'] }}",
            "select_option": [],
        },
    ),
    (
        Platform.SENSOR,
        {
            "state": "{{ 'yes' }}",
        },
    ),
    (
        Platform.SWITCH,
        {
            "state": "{{ 'on' }}",
            "turn_on": [],
            "turn_off": [],
        },
    ),
    (
        Platform.UPDATE,
        {
            "installed_version": "{{ '1.0' }}",
            "latest_version": "{{ '2.0' }}",
        },
    ),
    (
        Platform.VACUUM,
        {
            "state": "{{ 'docked' }}",
            "start": [],
        },
    ),
    (
        Platform.WEATHER,
        {
            "condition": "{{ 'cloudy' }}",
            "temperature": "{{ 20 }}",
            "humidity": "{{ 50 }}",
        },
    ),
]


@pytest.mark.parametrize(("platform", "config"), TRIGGER_PLATFORM_CONFIGURATIONS)
async def test_trigger_schema_with_conditions(
    hass: HomeAssistant,
    platform: Platform,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test conditions schema with valid and invalid configurations."""

    await setup_entity(
        hass,
        TemplatePlatformSetup(
            platform, "test_entity", make_test_trigger("sensor.test_state")
        ),
        ConfigurationStyle.TRIGGER,
        1,
        {
            "conditions": {
                "condition": "template",
                "value_template": "{{ 1 == 1 }}",
            },
            **config,
        },
    )

    assert "ERROR" not in caplog.text


@pytest.mark.parametrize(
    ("platform", "config"),
    [
        (
            Platform.BUTTON,
            {
                "press": [],
            },
        ),
    ],
)
async def test_invalid_trigger_schema_with_conditions(
    hass: HomeAssistant,
    platform: Platform,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test conditions schema with valid and invalid configurations."""

    await setup_entity(
        hass,
        TemplatePlatformSetup(
            platform, "test_entity", make_test_trigger("sensor.test_state")
        ),
        ConfigurationStyle.TRIGGER,
        0,
        {
            "conditions": {
                "condition": "template",
                "value_template": "{{ 1 == 1 }}",
            },
            **config,
        },
    )

    error = (
        "Invalid config for 'template': Unsupported option(s) found for domain button"
    )
    assert error in caplog.text


@pytest.mark.parametrize(
    ("platform", "config"),
    [
        (
            Platform.ALARM_CONTROL_PANEL,
            {
                "state": "{{ 'disarmed' }}",
            },
        ),
        (
            Platform.BINARY_SENSOR,
            {
                "state": "{{ 'on' }}",
            },
        ),
        (
            Platform.COVER,
            {
                "state": "{{ 'open' }}",
                "open_cover": [],
                "close_cover": [],
            },
        ),
        (
            Platform.DEVICE_TRACKER,
            {
                "in_zones": "{{ ['zone.home'] }}",
            },
        ),
        (
            Platform.EVENT,
            {
                "event_type": "{{ 'single' }}",
                "event_types": "{{ ['single'] }}",
            },
        ),
        (
            Platform.FAN,
            {
                "state": "{{ 'on' }}",
                "turn_on": [],
                "turn_off": [],
            },
        ),
        (
            Platform.IMAGE,
            {
                "url": "{{ 'http://www.test.com' }}",
            },
        ),
        (
            Platform.LIGHT,
            {
                "state": "{{ 'on' }}",
                "turn_on": [],
                "turn_off": [],
            },
        ),
        (
            Platform.LOCK,
            {
                "state": "{{ 'on' }}",
                "lock": [],
                "unlock": [],
            },
        ),
        (
            Platform.NUMBER,
            {
                "state": "{{ 4 }}",
                "min": "0",
                "max": "100",
                "step": "0.1",
                "unit_of_measurement": "cm",
                "set_value": [],
            },
        ),
        (
            Platform.SELECT,
            {
                "state": "{{ 'on' }}",
                "options": "{{ ['off', 'on', 'auto'] }}",
                "select_option": [],
            },
        ),
        (
            Platform.SENSOR,
            {
                "state": "{{ 'yes' }}",
            },
        ),
        (
            Platform.SWITCH,
            {
                "state": "{{ 'on' }}",
                "turn_on": [],
                "turn_off": [],
            },
        ),
        (
            Platform.UPDATE,
            {
                "installed_version": "{{ '1.0' }}",
                "latest_version": "{{ '2.0' }}",
            },
        ),
        (
            Platform.VACUUM,
            {
                "state": "{{ 'docked' }}",
                "start": [],
            },
        ),
        (
            Platform.WEATHER,
            {
                "condition": "{{ 'cloudy' }}",
                "temperature": "{{ 20 }}",
                "humidity": "{{ 50 }}",
            },
        ),
    ],
)
async def test_trigger_schema_with_invalid_condition(
    hass: HomeAssistant,
    platform: Platform,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test conditions schema with valid and invalid configurations."""

    await setup_entity(
        hass,
        TemplatePlatformSetup(
            platform, "test_entity", make_test_trigger("sensor.test_state")
        ),
        ConfigurationStyle.TRIGGER,
        1,
        {
            "conditions": {
                "condition": "device",
                "type": "is_off",
                "device_id": "70c5f67ec2f82f9ba128fe6e99eb7dfa",
                "entity_id": "c7e6f3753cb18937f2147bbbdccdd949",
                "domain": "light",
            },
            **config,
        },
    )

    assert len(hass.states.async_entity_ids(platform)) == 0
    assert (
        "The condition for test_entity failed to setup: Unknown device '70c5f67ec2f82f9ba128fe6e99eb7dfa'"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("platform", "config"),
    [
        (
            Platform.ALARM_CONTROL_PANEL,
            {
                "state": "{{ 'disarmed' }}",
            },
        ),
        (
            Platform.BINARY_SENSOR,
            {
                "state": "{{ 'on' }}",
            },
        ),
        (
            Platform.BUTTON,
            {
                "press": [],
            },
        ),
        (
            Platform.COVER,
            {
                "state": "{{ 'open' }}",
                "open_cover": [],
                "close_cover": [],
            },
        ),
        (
            Platform.DEVICE_TRACKER,
            {
                "in_zones": "{{ ['zone.home'] }}",
            },
        ),
        (
            Platform.EVENT,
            {
                "event_type": "{{ 'single' }}",
                "event_types": "{{ ['single'] }}",
            },
        ),
        (
            Platform.FAN,
            {
                "state": "{{ 'on' }}",
                "turn_on": [],
                "turn_off": [],
            },
        ),
        (
            Platform.IMAGE,
            {
                "url": "{{ 'http://www.test.com' }}",
            },
        ),
        (
            Platform.LIGHT,
            {
                "state": "{{ 'on' }}",
                "turn_on": [],
                "turn_off": [],
            },
        ),
        (
            Platform.LOCK,
            {
                "state": "{{ 'on' }}",
                "lock": [],
                "unlock": [],
            },
        ),
        (
            Platform.NUMBER,
            {
                "state": "{{ 4 }}",
                "min": "0",
                "max": "100",
                "step": "0.1",
                "unit_of_measurement": "cm",
                "set_value": [],
            },
        ),
        (
            Platform.SELECT,
            {
                "state": "{{ 'on' }}",
                "options": "{{ ['off', 'on', 'auto'] }}",
                "select_option": [],
            },
        ),
        (
            Platform.SENSOR,
            {
                "state": "{{ 'yes' }}",
            },
        ),
        (
            Platform.SWITCH,
            {
                "state": "{{ 'on' }}",
                "turn_on": [],
                "turn_off": [],
            },
        ),
        (
            Platform.UPDATE,
            {
                "installed_version": "{{ '1.0' }}",
                "latest_version": "{{ '2.0' }}",
            },
        ),
        (
            Platform.VACUUM,
            {
                "state": "{{ 'docked' }}",
                "start": [],
            },
        ),
        (
            Platform.WEATHER,
            {
                "condition": "{{ 'cloudy' }}",
                "temperature": "{{ 20 }}",
                "humidity": "{{ 50 }}",
            },
        ),
    ],
)
async def test_invalid_schema_with_conditions(
    hass: HomeAssistant,
    platform: Platform,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test conditions schema with valid and invalid configurations."""

    await setup_entity(
        hass,
        TemplatePlatformSetup(
            platform, "test_entity", make_test_trigger("sensor.test_state")
        ),
        ConfigurationStyle.MODERN,
        0,
        {
            "conditions": {
                "condition": "template",
                "value_template": "{{ 1 == 1 }}",
            },
            **config,
        },
    )

    error = (
        f"The conditions option for template {platform.replace('_', ' ')}: name: test_entity requires a trigger,"
        " remove the conditions option or rewrite configuration to use a trigger"
    )
    assert error in caplog.text


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (
            {
                "variables": {"a": 1},
                "button": {
                    "press": {
                        "service": "test.automation",
                        "data_template": {"caller": "{{ this.entity_id }}"},
                    },
                    "variables": {"b": 2},
                    "device_class": "restart",
                    "unique_id": "test",
                    "name": "test",
                    "icon": "mdi:test",
                },
            },
            {"a": 1, "b": 2},
        ),
        (
            {
                "variables": {"a": 1},
                "button": [
                    {
                        "press": {
                            "service": "test.automation",
                            "data_template": {"caller": "{{ this.entity_id }}"},
                        },
                        "variables": {"b": 2},
                        "device_class": "restart",
                        "unique_id": "test",
                        "name": "test",
                        "icon": "mdi:test",
                    }
                ],
            },
            {"a": 1, "b": 2},
        ),
        (
            {
                "variables": {"a": 1},
                "button": [
                    {
                        "press": {
                            "service": "test.automation",
                            "data_template": {"caller": "{{ this.entity_id }}"},
                        },
                        "variables": {"a": 2, "b": 2},
                        "device_class": "restart",
                        "unique_id": "test",
                        "name": "test",
                        "icon": "mdi:test",
                    }
                ],
            },
            {"a": 2, "b": 2},
        ),
        (
            {
                "variables": {"a": 1},
                "button": {
                    "press": {
                        "service": "test.automation",
                        "data_template": {"caller": "{{ this.entity_id }}"},
                    },
                    "device_class": "restart",
                    "unique_id": "test",
                    "name": "test",
                    "icon": "mdi:test",
                },
            },
            {"a": 1},
        ),
        (
            {
                "button": {
                    "press": {
                        "service": "test.automation",
                        "data_template": {"caller": "{{ this.entity_id }}"},
                    },
                    "variables": {"b": 2},
                    "device_class": "restart",
                    "unique_id": "test",
                    "name": "test",
                    "icon": "mdi:test",
                },
            },
            {"b": 2},
        ),
    ],
)
async def test_combined_state_variables(
    hass: HomeAssistant, config: dict, expected: dict
) -> None:
    """Tests combining variables for state based template entities."""
    validated = await async_validate_config_section(hass, config)
    assert "variables" not in validated
    variables: ScriptVariables = validated["button"][0]["variables"]
    assert variables.as_dict() == expected


async def test_trigger_variables_schema(hass: HomeAssistant) -> None:
    """Test trigger variables are validated as script variables."""
    validated = CONFIG_SECTION_SCHEMA(
        {
            "triggers": {"trigger": "event", "event_type": "my_event"},
            "trigger_variables": {"a": 1, "b": "two"},
            "sensor": {"name": "test", "state": "{{ b }}"},
        }
    )
    trigger_variables: ScriptVariables = validated["trigger_variables"]
    assert isinstance(trigger_variables, ScriptVariables)
    assert trigger_variables.as_dict() == {"a": 1, "b": "two"}


async def test_trigger_variables_requires_trigger(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test trigger variables without a trigger logs an error."""
    with assert_setup_component(0, DOMAIN):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    "trigger_variables": {"a": 1},
                    "sensor": {"name": "test", "state": "{{ 1 }}"},
                }
            },
        )

    assert (
        "The trigger_variables option requires a trigger, remove the"
        " trigger_variables option or rewrite configuration to use a trigger"
    ) in caplog.text


@pytest.mark.parametrize(
    ("config", "expected_error"),
    [
        pytest.param(
            {
                "triggers": [
                    {"trigger": "event", "event_type": "valid"},
                    {"trigger": "not_a_platform"},
                ],
                "binary_sensor": {"name": "test", "state": "{{ true }}"},
            },
            "Invalid config for 'template':"
            " Invalid trigger 'not_a_platform' specified 'triggers->1', got"
            " {'platform': 'not_a_platform'}",
            id="trigger",
        ),
        pytest.param(
            {
                "triggers": {"trigger": "not_a_platform"},
                "binary_sensor": {"name": "test", "state": "{{ true }}"},
            },
            "Invalid config for 'template':"
            " Invalid trigger 'not_a_platform' specified 'triggers->0', got"
            " {'platform': 'not_a_platform'}",
            id="single_trigger",
        ),
        pytest.param(
            {
                "trigger": {"platform": "not_a_platform"},
                "binary_sensor": {"name": "test", "state": "{{ true }}"},
            },
            "Invalid config for 'template':"
            " Invalid trigger 'not_a_platform' specified 'triggers->0', got"
            " {'platform': 'not_a_platform'}",
            id="single_trigger_legacy_key",
        ),
        pytest.param(
            {
                "triggers": [
                    {
                        "triggers": [
                            {"trigger": "event", "event_type": "valid"},
                            {"trigger": "not_a_platform"},
                        ]
                    },
                    {"trigger": "event", "event_type": "also_valid"},
                ],
                "binary_sensor": {"name": "test", "state": "{{ true }}"},
            },
            "Invalid config for 'template':"
            " Invalid trigger 'not_a_platform' specified 'triggers->1', got"
            " {'platform': 'not_a_platform'}",
            id="trigger_sublist",
        ),
        pytest.param(
            {
                "use_blueprint": {
                    "path": "test_event_sensor.yaml",
                    "input": {"event_type": "state_reported", "event_data": {}},
                },
                "name": "test",
            },
            "Invalid config for 'template' at"
            " blueprints/template/test_event_sensor.yaml, line 19:"
            " Can't listen to state_reported in event trigger for dictionary value"
            " 'triggers->0->event_type', got 'state_reported'",
            id="blueprint_trigger",
        ),
        pytest.param(
            {
                "triggers": {"trigger": "event", "event_type": "valid"},
                "conditions": [
                    {
                        "condition": "state",
                        "entity_id": "sensor.foo",
                        "state": "on",
                    },
                    {
                        "condition": "state",
                        "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
                        "state": "on",
                    },
                ],
                "binary_sensor": {"name": "test", "state": "{{ true }}"},
            },
            "Invalid config for 'template':"
            " Unknown entity registry entry abcdabcdabcdabcdabcdabcdabcdabcd"
            " 'conditions->1', got {'condition': 'state',"
            " 'entity_id': ['abcdabcdabcdabcdabcdabcdabcdabcd'], 'state': 'on',"
            " 'match': 'all'}",
            id="condition",
        ),
        pytest.param(
            {
                "triggers": {"trigger": "event", "event_type": "valid"},
                "conditions": {
                    "condition": "state",
                    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "state": "on",
                },
                "binary_sensor": {"name": "test", "state": "{{ true }}"},
            },
            "Invalid config for 'template':"
            " Unknown entity registry entry abcdabcdabcdabcdabcdabcdabcdabcd"
            " 'conditions->0', got {'condition': 'state',"
            " 'entity_id': ['abcdabcdabcdabcdabcdabcdabcdabcd'], 'state': 'on',"
            " 'match': 'all'}",
            id="single_condition",
        ),
        pytest.param(
            {
                "triggers": {"trigger": "event", "event_type": "valid"},
                "conditions": {
                    "condition": "state",
                    "entity_id": "sensor.foo",
                    "state": "on",
                    "for": "invalid",
                },
                "binary_sensor": {"name": "test", "state": "{{ true }}"},
            },
            "Invalid config for 'template': offset invalid should be format 'HH:MM',"
            " 'HH:MM:SS' or 'HH:MM:SS.F' for dictionary value 'conditions->for',"
            " got 'invalid'",
            id="schema_error_single_condition",
        ),
    ],
)
async def test_setup_component_bad_config_logs_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config: dict,
    expected_error: str,
) -> None:
    """Test setting up template with a bad config logs a useful error message."""
    await async_setup_component(hass, "template", {"template": [config]})
    assert expected_error in caplog.text


@pytest.mark.parametrize(("platform", "config"), TRIGGER_PLATFORM_CONFIGURATIONS)
@pytest.mark.parametrize(
    ("extra_section_config", "breadcrumb"),
    [
        ({}, "template section"),
        ({"unique_id": "foo"}, "template section with unique_id: foo"),
    ],
)
async def test_trigger_schema_with_invalid_actions(
    hass: HomeAssistant,
    platform: Platform,
    config: ConfigType,
    extra_section_config: ConfigType,
    breadcrumb: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test trigger schema with invalid actions."""

    await setup_entity(
        hass,
        TemplatePlatformSetup(
            platform,
            "test_entity",
            {
                **extra_section_config,
                "trigger": [
                    {"trigger": "state", "entity_id": ["sensor.test_state"]},
                ],
                "action": [
                    {
                        "type": "turn_off",
                        "device_id": "70c5f67ec2f82f9ba128fe6e99eb7dfa",
                        "entity_id": "c7e6f3753cb18937f2147bbbdccdd949",
                        "domain": "light",
                    },
                ],
            },
        ),
        ConfigurationStyle.TRIGGER,
        1,
        config,
    )

    assert len(hass.states.async_entity_ids(platform)) == 0
    assert (
        f"The 'actions' for {breadcrumb} failed to setup: Unknown device '70c5f67ec2f82f9ba128fe6e99eb7dfa'"
        in caplog.text
    )


@pytest.mark.parametrize(("platform", "config"), TRIGGER_PLATFORM_CONFIGURATIONS)
async def test_trigger_schema_with_valid_actions(
    hass: HomeAssistant,
    platform: Platform,
    config: ConfigType,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    calls: list,
) -> None:
    """Test trigger schema with valid actions configurations."""

    platform_setup, device_entry, entity_entry = await setup_mock_devices(
        hass, platform, device_registry, entity_registry
    )

    await setup_entity(
        hass,
        TemplatePlatformSetup(
            platform,
            "test_entity",
            {
                "trigger": [
                    {"trigger": "state", "entity_id": ["sensor.test_state"]},
                ],
                **make_mock_device_actions(
                    ["actions"], platform_setup, device_entry, entity_entry
                ),
            },
        ),
        ConfigurationStyle.TRIGGER,
        1,
        config,
    )

    await async_trigger(hass, "sensor.test_state", "anything")
    assert_action(platform_setup, calls, 1, "fake_action")


@pytest.mark.parametrize(
    ("config", "expected_root", "expected_entity"),
    [
        (
            {
                "trigger": {"trigger": "event", "event_type": "my_event"},
                "variables": {"a": 1},
                "binary_sensor": {
                    "name": "test",
                    "state": "{{ trigger.event.event_type }}",
                    "variables": {"b": 2},
                },
            },
            {"a": 1},
            {"b": 2},
        ),
        (
            {
                "triggers": {"trigger": "event", "event_type": "my_event"},
                "variables": {"a": 1},
                "binary_sensor": {
                    "name": "test",
                    "state": "{{ trigger.event.event_type }}",
                },
            },
            {"a": 1},
            {},
        ),
        (
            {
                "trigger": {"trigger": "event", "event_type": "my_event"},
                "binary_sensor": {
                    "name": "test",
                    "state": "{{ trigger.event.event_type }}",
                    "variables": {"b": 2},
                },
            },
            {},
            {"b": 2},
        ),
    ],
)
async def test_combined_trigger_variables(
    hass: HomeAssistant,
    config: dict,
    expected_root: dict,
    expected_entity: dict,
) -> None:
    """Tests variable are not combined for trigger based template entities."""
    empty = ScriptVariables({})
    validated = await async_validate_config_section(hass, config)
    root_variables: ScriptVariables = validated.get("variables", empty)
    assert root_variables.as_dict() == expected_root
    variables: ScriptVariables = validated["binary_sensor"][0].get("variables", empty)
    assert variables.as_dict() == expected_entity


async def test_state_init_attribute_variables(
    hass: HomeAssistant,
) -> None:
    """Test state based template entity initializes attributes with variables."""
    source = "switch.foo"
    entity_id = "sensor.foo"

    hass.states.async_set(source, "on", {"friendly_name": "Foo"})
    config = {
        "template": [
            {
                "variables": {
                    "switch": "switch.foo",
                    "on_icon": "mdi:lightbulb",
                    "on_picture": "on.png",
                },
                "sensor": {
                    "variables": {
                        "off_icon": "mdi:lightbulb-off",
                        "off_picture": "off.png",
                    },
                    "name": "{{ state_attr(switch, 'friendly_name') }}",
                    "icon": "{{ on_icon if is_state(switch, 'on') else off_icon }}",
                    "picture": (
                        "{{ on_picture if is_state(switch, 'on') else off_picture }}"
                    ),
                    "state": "{{ is_state(switch, 'on') }}",
                },
            }
        ],
    }
    assert await async_setup_component(
        hass,
        DOMAIN,
        config,
    )
    await hass.async_block_till_done()

    # Check initial state
    sensor = hass.states.get(entity_id)
    assert sensor
    assert sensor.state == "True"
    assert sensor.attributes["icon"] == "mdi:lightbulb"
    assert sensor.attributes["entity_picture"] == "on.png"
    assert sensor.attributes["friendly_name"] == "Foo"

    hass.states.async_set(source, "off", {"friendly_name": "Foo"})
    await hass.async_block_till_done()

    # Check to see that the template light works
    sensor = hass.states.get(entity_id)
    assert sensor
    assert sensor.state == "False"
    assert sensor.attributes["icon"] == "mdi:lightbulb-off"
    assert sensor.attributes["entity_picture"] == "off.png"
    assert sensor.attributes["friendly_name"] == "Foo"


@pytest.mark.parametrize(
    ("config", "expected_warning"),
    [
        (
            {
                "trigger": {"trigger": "event", "event_type": "my_event"},
            },
            "Invalid template configuration found, trigger option is"
            " missing matching domain",
        ),
        (
            {
                "action": {
                    "service": "test.automation",
                    "data_template": {"caller": "{{ this.entity_id }}"},
                },
                "sensor": {
                    "state": "{{ states('sensor.test') }}",
                    "unique_id": "test",
                    "name": "test",
                    "icon": "mdi:test",
                },
            },
            "Invalid template configuration found, action option requires a trigger",
        ),
    ],
)
async def test_invalid_schema_raises_issue(
    hass: HomeAssistant,
    config: dict,
    expected_warning: str,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid config schemas create issue and log warning."""

    await async_setup_component(hass, DOMAIN, {"template": [config]})

    assert expected_warning in caplog.text

    assert len(issue_registry.issues) == 1
    issue = next(iter(issue_registry.issues.values()))

    assert issue.domain == "template"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_multiple_configuration_keys(
    hass: HomeAssistant,
) -> None:
    """Test multiple configurations keys create entities."""
    await async_setup_component(
        hass,
        DOMAIN,
        {
            "template": [{"binary_sensor": [{"name": "Foo", "state": "{{ True }}"}]}],
            "template mytemplates": [
                {
                    "sensor": [
                        {"name": "Foo", "state": "{{ 'bar' }}"},
                        {"name": "Bar", "state": "{{ 'foo' }}"},
                    ]
                }
            ],
            "template y": [
                {
                    "cover": [
                        {
                            "name": "Shades Curtain",
                            "unique_id": "shades_curtain",
                            "open_cover": [],
                            "close_cover": [],
                            "stop_cover": [],
                        }
                    ]
                },
                {
                    "cover": [
                        {
                            "open_cover": {
                                "target": {"entity_id": ["cover.shades_curtain"]},
                                "action": "cover.close_cover",
                            },
                            "close_cover": {
                                "target": {"entity_id": ["cover.shades_curtain"]},
                                "action": "cover.open_cover",
                            },
                            "stop_cover": {
                                "target": {"entity_id": ["cover.shades_curtain"]},
                                "action": "cover.stop_cover",
                            },
                            "default_entity_id": "cover.shades_reversed",
                            "icon": (
                                "{% set s = states('cover.shades_curtain') %}\n"
                                "{% if s == 'open' %}\n"
                                "   mdi:curtains-closed\n"
                                "{% else %}\n"
                                "   mdi:curtains\n"
                                "{% endif %}"
                            ),
                            "name": "Shades Reversed",
                            "unique_id": "c0223bcb-32c6-430e-a2c1-3545f8031796",
                            "state": (
                                "{% set s = states('cover.shades_curtain') %}\n"
                                "{% if s == 'open' %}\n  closed\n"
                                "{% elif s == 'closed' %}\n  open\n"
                                "{% elif s == 'opening' %}\n  closing\n"
                                "{% elif s == 'closing' %}\n  opening\n"
                                "{% else %}\n  unknown\n{% endif %}"
                            ),
                        }
                    ]
                },
            ],
        },
    )
    await hass.async_block_till_done()

    for entity_id, expected in (
        ("binary_sensor.foo", "on"),
        ("sensor.foo", "bar"),
        ("sensor.bar", "foo"),
        ("cover.shades_curtain", "unknown"),
        ("cover.shades_reversed", "unknown"),
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected


async def async_setup_yaml_config(
    hass: HomeAssistant, config_dir: Path, yaml_config: str
) -> None:
    """Write configuration.yaml and set up the template integration from it."""
    yaml_path = config_dir / "configuration.yaml"
    await hass.async_add_executor_job(yaml_path.write_text, yaml_config)
    config = await hass.async_add_executor_job(load_yaml_dict, yaml_path)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def async_reload_yaml_config(
    hass: HomeAssistant, config_dir: Path, yaml_config: str
) -> None:
    """Write configuration.yaml and reload the template integration from it."""
    yaml_path = config_dir / "configuration.yaml"
    await hass.async_add_executor_job(yaml_path.write_text, yaml_config)
    with patch.object(hass_config, "YAML_CONFIG_FILE", str(yaml_path)):
        await hass.services.async_call(DOMAIN, TemplateService.RELOAD, blocking=True)
    await hass.async_block_till_done()


WEATHER_LEGACY_YAML = """\
template:
  - weather:
      - name: Test
        condition_template: sunny
        temperature_template: "{{ 20 }}"
        humidity_template: "{{ 25 }}"
"""


WEATHER_SECOND_LEGACY_YAML = """\
      - unique_id: second
        condition_template: cloudy
        temperature_template: "{{ 10 }}"
        humidity_template: "{{ 50 }}"
"""


def legacy_options(first_line: int) -> str:
    """Return the repair options of a legacy weather entity starting at a line."""
    return (
        f"- `configuration.yaml:{first_line}`: `condition_template` → `condition`\n"
        f"- `configuration.yaml:{first_line + 1}`: "
        "`temperature_template` → `temperature`\n"
        f"- `configuration.yaml:{first_line + 2}`: `humidity_template` → `humidity`"
    )


@pytest.fixture
def yaml_config_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Use a temporary configuration directory."""
    hass.config.config_dir = str(tmp_path)
    return tmp_path


async def test_deprecated_template_options_issue_file_and_line(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, yaml_config_dir: Path
) -> None:
    """Test the repair lists file and line, and is removed after a fix."""
    await async_setup_yaml_config(hass, yaml_config_dir, WEATHER_LEGACY_YAML)

    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert [issue.translation_placeholders for issue in issues] == [
        {"identifier": "name: Test", "options": legacy_options(4)},
    ]

    await async_reload_yaml_config(
        hass,
        yaml_config_dir,
        WEATHER_LEGACY_YAML.replace("_template:", ":"),
    )

    assert (
        get_issues_with_prefix(
            issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
        )
        == []
    )


async def test_deprecated_template_options_issue_per_entity(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, yaml_config_dir: Path
) -> None:
    """Test a repair is created for each weather entity with deprecated options."""
    await async_setup_yaml_config(
        hass,
        yaml_config_dir,
        WEATHER_LEGACY_YAML
        + WEATHER_SECOND_LEGACY_YAML
        + """\
      - name: Modern
        condition: sunny
        temperature: "{{ 20 }}"
        humidity: "{{ 25 }}"
""",
    )

    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert [issue.translation_placeholders for issue in issues] == [
        {"identifier": "name: Test", "options": legacy_options(4)},
        {"identifier": "unique_id: second", "options": legacy_options(8)},
    ]


async def test_deprecated_template_options_issue_one_entity_fixed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, yaml_config_dir: Path
) -> None:
    """Test fixing one entity only removes its repair and keeps the ignore flag."""
    await async_setup_yaml_config(
        hass, yaml_config_dir, WEATHER_LEGACY_YAML + WEATHER_SECOND_LEGACY_YAML
    )
    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert [issue.translation_placeholders for issue in issues] == [
        {"identifier": "name: Test", "options": legacy_options(4)},
        {"identifier": "unique_id: second", "options": legacy_options(8)},
    ]
    second_issue_id = issues[1].issue_id
    issue_registry.async_ignore(DOMAIN, second_issue_id, True)
    second_issue = issue_registry.async_get_issue(DOMAIN, second_issue_id)

    await async_reload_yaml_config(
        hass,
        yaml_config_dir,
        WEATHER_LEGACY_YAML.replace("_template:", ":") + WEATHER_SECOND_LEGACY_YAML,
    )

    assert get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    ) == [second_issue]


async def test_deprecated_template_options_issue_section_unique_id(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, yaml_config_dir: Path
) -> None:
    """Test the repair labels the entity as written, without the section unique_id."""
    await async_setup_yaml_config(
        hass,
        yaml_config_dir,
        """\
template:
  - unique_id: first_floor
    weather:
      - unique_id: kitchen
        condition_template: sunny
        temperature_template: "{{ 20 }}"
        humidity_template: "{{ 25 }}"
""",
    )

    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert [issue.translation_placeholders for issue in issues] == [
        {"identifier": "unique_id: kitchen", "options": legacy_options(5)},
    ]


async def test_deprecated_template_options_issue_same_name(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, yaml_config_dir: Path
) -> None:
    """Test entities sharing a name but not a unique_id have separate repairs."""
    await async_setup_yaml_config(
        hass,
        yaml_config_dir,
        """\
template:
  - weather:
      - name: Test
        unique_id: first
        condition_template: sunny
        temperature_template: "{{ 20 }}"
        humidity_template: "{{ 25 }}"
      - name: Test
        unique_id: second
        condition_template: sunny
        temperature_template: "{{ 20 }}"
        humidity_template: "{{ 25 }}"
""",
    )

    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert [issue.translation_placeholders for issue in issues] == [
        {"identifier": "name: Test", "options": legacy_options(5)},
        {"identifier": "name: Test", "options": legacy_options(10)},
    ]
    issue_registry.async_ignore(DOMAIN, issues[1].issue_id, True)
    second_issue = issue_registry.async_get_issue(DOMAIN, issues[1].issue_id)

    await async_reload_yaml_config(
        hass,
        yaml_config_dir,
        """\
template:
  - weather:
      - name: Test
        unique_id: first
        condition: sunny
        temperature: "{{ 20 }}"
        humidity: "{{ 25 }}"
      - name: Test
        unique_id: second
        condition_template: sunny
        temperature_template: "{{ 20 }}"
        humidity_template: "{{ 25 }}"
""",
    )

    assert get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    ) == [second_issue]


async def test_deprecated_template_options_issue_dismissed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, yaml_config_dir: Path
) -> None:
    """Test a dismissed repair stays dismissed until the configuration changes."""
    await async_setup_yaml_config(hass, yaml_config_dir, WEATHER_LEGACY_YAML)
    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert len(issues) == 1
    dismissed_issue_id = issues[0].issue_id
    issue_registry.async_ignore(DOMAIN, dismissed_issue_id, True)

    # Moving the options to other lines is not a configuration change
    await async_reload_yaml_config(hass, yaml_config_dir, "\n" + WEATHER_LEGACY_YAML)

    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert len(issues) == 1
    assert issues[0].issue_id == dismissed_issue_id
    assert issues[0].dismissed_version is not None

    await async_reload_yaml_config(
        hass, yaml_config_dir, WEATHER_LEGACY_YAML.replace("sunny", "cloudy")
    )

    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert len(issues) == 1
    assert issues[0].issue_id != dismissed_issue_id
    assert issues[0].dismissed_version is None


async def test_deprecated_template_options_issue_not_changed_by_config_check(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, yaml_config_dir: Path
) -> None:
    """Test validating the configuration without reloading keeps the repair."""
    await async_setup_yaml_config(hass, yaml_config_dir, WEATHER_LEGACY_YAML)
    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert len(issues) == 1

    # A configuration check validates the fixed configuration without applying it
    yaml_path = yaml_config_dir / "configuration.yaml"
    await hass.async_add_executor_job(
        yaml_path.write_text, WEATHER_LEGACY_YAML.replace("_template:", ":")
    )
    fixed_config = await hass.async_add_executor_job(load_yaml_dict, yaml_path)
    await async_validate_config(hass, fixed_config)

    assert (
        get_issues_with_prefix(
            issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
        )
        == issues
    )


@pytest.mark.parametrize(
    "invalid_yaml",
    [
        pytest.param(
            WEATHER_LEGACY_YAML + "        invalid_option: true\n",
            id="only_section",
        ),
        pytest.param(
            WEATHER_LEGACY_YAML
            + """\
        invalid_option: true
  - sensor:
      - state: "{{ 1 }}"
""",
            id="with_valid_section",
        ),
    ],
)
async def test_deprecated_template_options_issue_kept_with_invalid_section(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    yaml_config_dir: Path,
    invalid_yaml: str,
) -> None:
    """Test an invalid section doesn't delete repairs or their ignore flag."""
    await async_setup_yaml_config(hass, yaml_config_dir, WEATHER_LEGACY_YAML)
    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert len(issues) == 1
    issue_registry.async_ignore(DOMAIN, issues[0].issue_id, True)
    issue = issue_registry.async_get_issue(DOMAIN, issues[0].issue_id)

    await async_reload_yaml_config(hass, yaml_config_dir, invalid_yaml)

    assert get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    ) == [issue]

    await async_reload_yaml_config(hass, yaml_config_dir, WEATHER_LEGACY_YAML)

    assert get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    ) == [issue]


async def test_deprecated_template_options_issue_removed_without_template_config(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, yaml_config_dir: Path
) -> None:
    """Test the repair is removed when the template configuration is removed."""
    await async_setup_yaml_config(hass, yaml_config_dir, WEATHER_LEGACY_YAML)
    assert get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )

    await async_reload_yaml_config(hass, yaml_config_dir, "homeassistant:\n")

    assert (
        get_issues_with_prefix(
            issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
        )
        == []
    )


async def test_deprecated_template_options_issue_identical_entities(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, yaml_config_dir: Path
) -> None:
    """Test identical entities without a unique_id share one repair."""
    await async_setup_yaml_config(
        hass,
        yaml_config_dir,
        """\
template:
  - weather:
      - name: Test
        condition_template: sunny
        temperature_template: "{{ 20 }}"
        humidity_template: "{{ 25 }}"
      - name: Test
        condition_template: sunny
        temperature_template: "{{ 20 }}"
        humidity_template: "{{ 25 }}"
""",
    )

    issues = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert [issue.translation_placeholders for issue in issues] == [
        {
            "identifier": "name: Test",
            "options": f"{legacy_options(4)}\n{legacy_options(8)}",
        },
    ]
    issue_registry.async_ignore(DOMAIN, issues[0].issue_id, True)
    dismissed_issue = issue_registry.async_get_issue(DOMAIN, issues[0].issue_id)
    assert dismissed_issue is not None

    await async_reload_yaml_config(
        hass,
        yaml_config_dir,
        """\
template:
  - weather:
      - name: Test
        condition: sunny
        temperature: "{{ 20 }}"
        humidity: "{{ 25 }}"
      - name: Test
        condition_template: sunny
        temperature_template: "{{ 20 }}"
        humidity_template: "{{ 25 }}"
""",
    )

    remaining = get_issues_with_prefix(
        issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
    )
    assert [
        (issue.issue_id, issue.dismissed_version, issue.translation_placeholders)
        for issue in remaining
    ] == [
        (
            dismissed_issue.issue_id,
            dismissed_issue.dismissed_version,
            {"identifier": "name: Test", "options": legacy_options(8)},
        )
    ]


async def test_deprecated_template_options_issue_blueprint(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test all instances of a blueprint share one repair."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "use_blueprint": {
                        "path": "test_weather_with_variables.yaml",
                        "input": {"sensor": sensor},
                    },
                    **name,
                }
                for sensor, name in (
                    ("sensor.first", {"name": "Named"}),
                    ("sensor.second", {}),
                    ("sensor.third", {}),
                )
            ]
        },
    )
    await hass.async_block_till_done()

    assert (
        get_issues_with_prefix(
            issue_registry, WEATHER_DEPRECATED_OPTIONS.translation_key
        )
        == snapshot
    )


def test_merge_deprecated_options_per_platform() -> None:
    """Test deprecations of the same platform all keep their option locations."""
    deprecations = [
        DeprecatedTemplateOptions(
            platform=platform,
            options=options,
            translation_key=key,
            blueprint_translation_key=f"{key}_blueprint",
            breaks_in_ha_version="2027.6.0",
        )
        for platform, options, key in (
            (Platform.LIGHT, {"temperature": "temperature_kelvin"}, "first"),
            (Platform.LIGHT, {"level": "set_level"}, "second"),
            (Platform.COVER, {"position": "set_cover_position"}, "third"),
        )
    ]

    assert _merge_deprecated_options(deprecations) == {
        Platform.LIGHT: {"temperature", "level"},
        Platform.COVER: {"position"},
    }


async def test_option_locations_only_deprecated_options(
    hass: HomeAssistant, yaml_config_dir: Path
) -> None:
    """Test only the deprecated options of opted in platforms keep a location."""
    yaml_path = yaml_config_dir / "configuration.yaml"
    await hass.async_add_executor_job(
        yaml_path.write_text,
        WEATHER_LEGACY_YAML
        + """\
  - sensor:
      - name: Sensor
        state: "{{ 1 }}"
""",
    )
    config = await hass.async_add_executor_job(load_yaml_dict, yaml_path)

    validated = await async_validate_config(hass, config)

    assert [section.option_locations for section in validated[DOMAIN]] == [
        {
            "weather": [
                {
                    "condition_template": (str(yaml_path), 4),
                    "temperature_template": (str(yaml_path), 5),
                    "humidity_template": (str(yaml_path), 6),
                }
            ]
        },
        {},
    ]
