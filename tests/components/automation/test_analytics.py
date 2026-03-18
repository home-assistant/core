"""Tests for analytics platform."""

import pytest

from homeassistant.components.analytics import async_devices_payload
from homeassistant.components.automation import DOMAIN
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
        domain="automation",
        platform="automation",
        unique_id="automation1",
        suggested_object_id="automation1",
        capabilities={"id": "automation1"},
    )

    result = await async_devices_payload(hass)
    assert result["integrations"][DOMAIN]["entities"] == [
        {
            "assumed_state": None,
            "capabilities": None,
            "domain": "automation",
            "entity_category": None,
            "has_entity_name": False,
            "modified_by_integration": [
                "capabilities",
            ],
            "original_device_class": None,
            "unit_of_measurement": None,
        },
    ]
