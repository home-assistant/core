"""Test Template config."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.components.template.config import CONFIG_SECTION_SCHEMA
from homeassistant.core import HomeAssistant


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
