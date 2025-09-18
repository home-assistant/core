"""Test Template config."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.components.template.config import CONFIG_SECTION_SCHEMA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template


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
