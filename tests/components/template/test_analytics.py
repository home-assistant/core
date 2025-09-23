"""Tests for analytics platform."""

import pytest

from homeassistant.components.analytics import async_devices_payload
from homeassistant.components.template import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.mark.asyncio
async def test_analytics(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the analytics platform."""
    await async_setup_component(hass, "analytics", {})

    entity_registry.async_get_or_create(
        domain=Platform.FAN,
        platform="template",
        unique_id="fan1",
        suggested_object_id="my_fan",
        capabilities={"options": ["a", "b", "c"], "preset_modes": ["auto", "eco"]},
    )
    entity_registry.async_get_or_create(
        domain=Platform.SELECT,
        platform="template",
        unique_id="select1",
        suggested_object_id="my_select",
        capabilities={"not_filtered": "xyz", "options": ["a", "b", "c"]},
    )
    entity_registry.async_get_or_create(
        domain=Platform.SELECT,
        platform="template",
        unique_id="select2",
        suggested_object_id="my_select",
        capabilities={"not_filtered": "xyz"},
    )
    entity_registry.async_get_or_create(
        domain=Platform.LIGHT,
        platform="template",
        unique_id="light1",
        suggested_object_id="my_light",
        capabilities={"not_filtered": "abc"},
    )

    result = await async_devices_payload(hass)
    assert result["integrations"][DOMAIN]["entities"] == [
        {
            "assumed_state": None,
            "capabilities": {
                "options": ["a", "b", "c"],
                "preset_modes": 2,
            },
            "domain": "fan",
            "entity_category": None,
            "has_entity_name": False,
            "modified_by_integration": [
                "capabilities",
            ],
            "original_device_class": None,
            "unit_of_measurement": None,
        },
        {
            "assumed_state": None,
            "capabilities": {
                "not_filtered": "xyz",
                "options": 3,
            },
            "domain": "select",
            "entity_category": None,
            "has_entity_name": False,
            "modified_by_integration": [
                "capabilities",
            ],
            "original_device_class": None,
            "unit_of_measurement": None,
        },
        {
            "assumed_state": None,
            "capabilities": {
                "not_filtered": "xyz",
            },
            "domain": "select",
            "entity_category": None,
            "has_entity_name": False,
            "modified_by_integration": None,
            "original_device_class": None,
            "unit_of_measurement": None,
        },
        {
            "assumed_state": None,
            "capabilities": {
                "not_filtered": "abc",
            },
            "domain": "light",
            "entity_category": None,
            "has_entity_name": False,
            "modified_by_integration": None,
            "original_device_class": None,
            "unit_of_measurement": None,
        },
    ]
