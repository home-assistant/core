"""Test Template config."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.components.template import DOMAIN
from homeassistant.components.template.config import (
    CONFIG_SECTION_SCHEMA,
    async_validate_config_section,
)
from homeassistant.core import HomeAssistant
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


async def test_state_init_attribute_variables(
    hass: HomeAssistant,
) -> None:
    """Test a state based template entity initializes icon, name, and picture with variables."""
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
                    "picture": "{{ on_picture if is_state(switch, 'on') else off_picture }}",
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
