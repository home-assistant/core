"""Test Template config."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.components.template.config import (
    CONFIG_SECTION_SCHEMA,
    async_validate_config_section,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component


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
    ],
)
async def test_invalid_schema(hass: HomeAssistant, config: dict) -> None:
    """Test invalid config schemas."""
    with pytest.raises(vol.Invalid):
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
    with pytest.raises(vol.Invalid):
        CONFIG_SECTION_SCHEMA(config)


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


@pytest.mark.parametrize(
    ("config", "expected_warning"),
    [
        (
            {
                "trigger": {"trigger": "event", "event_type": "my_event"},
            },
            "Invalid template configuration found, trigger option is missing matching domain",
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

    await async_setup_component(hass, "template", {"template": [config]})

    assert expected_warning in caplog.text

    assert len(issue_registry.issues) == 1
    issue = next(iter(issue_registry.issues.values()))

    assert issue.domain == "template"
    assert issue.severity == ir.IssueSeverity.WARNING
