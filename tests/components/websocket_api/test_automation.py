"""Tests for the websocket automation helpers."""

from homeassistant.components.websocket_api.automation import (
    _AutomationComponentLookupData,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import TargetSelector


async def test_translation_key_filter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a translation key filter matches entities carrying that key."""
    entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique",
        suggested_object_id="current_hour",
        translation_key="epex_current_hour",
    )
    other_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "other_unique",
        suggested_object_id="next_hour",
        translation_key="epex_next_hour",
    )
    target = TargetSelector.CONFIG_SCHEMA(
        {
            "entity": [
                {
                    "integration": "test",
                    "domain": "sensor",
                    "translation_key": "epex_current_hour",
                }
            ]
        }
    )
    lookup = _AutomationComponentLookupData.create("test.trigger", target)

    assert lookup.matches(hass, entry.entity_id, "sensor", "test", False)
    assert not lookup.matches(hass, other_entry.entity_id, "sensor", "test", False)
    assert not lookup.matches(hass, "sensor.unregistered", "sensor", "test", False)


async def test_entity_filter_without_translation_key(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a filter without a translation key still matches any registered entity."""
    entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique",
        suggested_object_id="current_hour",
        translation_key="epex_current_hour",
    )
    target = TargetSelector.CONFIG_SCHEMA(
        {"entity": [{"integration": "test", "domain": "sensor"}]}
    )
    lookup = _AutomationComponentLookupData.create("test.trigger", target)

    assert lookup.matches(hass, entry.entity_id, "sensor", "test", False)


async def test_translation_key_only_filter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a filter with only a translation key matches entities of any integration."""
    entry = entity_registry.async_get_or_create(
        "sensor",
        "other_test",
        "unique",
        suggested_object_id="current_hour",
        translation_key="epex_current_hour",
    )
    other_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "other_unique",
        suggested_object_id="next_hour",
        translation_key="epex_next_hour",
    )
    target = TargetSelector.CONFIG_SCHEMA(
        {"entity": [{"translation_key": "epex_current_hour"}]}
    )
    lookup = _AutomationComponentLookupData.create("test.trigger", target)

    assert lookup.matches(hass, entry.entity_id, "sensor", "other_test", False)
    assert not lookup.matches(hass, other_entry.entity_id, "sensor", "test", False)
