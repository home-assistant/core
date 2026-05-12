"""Test exposed entities template functions."""

from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.helpers.template.helpers import assert_result_info, render_to_info


async def test_exposed_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test exposed_entities function."""
    assert await async_setup_component(hass, "homeassistant", {})

    # Test no exposed entities
    info = render_to_info(hass, "{{ exposed_entities('conversation') }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # Create some entities
    entry1 = entity_registry.async_get_or_create("light", "test", "entity1")
    entry2 = entity_registry.async_get_or_create("switch", "test", "entity2")
    entry3 = entity_registry.async_get_or_create("binary_sensor", "test", "entity3")

    # Expose some entities to conversation assistant
    async_expose_entity(hass, "conversation", entry1.entity_id, True)
    async_expose_entity(hass, "conversation", entry2.entity_id, True)

    async_expose_entity(hass, "conversation", entry3.entity_id, False)

    info = render_to_info(hass, "{{ exposed_entities('conversation') }}")
    assert_result_info(info, [entry1.entity_id, entry2.entity_id])
    assert info.rate_limit is None


async def test_exposed_entities_as_filter(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test exposed_entities as a filter."""
    assert await async_setup_component(hass, "homeassistant", {})

    entry1 = entity_registry.async_get_or_create("light", "test", "entity1")
    entry2 = entity_registry.async_get_or_create("switch", "test", "entity2")

    async_expose_entity(hass, "conversation", entry1.entity_id, True)
    async_expose_entity(hass, "conversation", entry2.entity_id, True)

    info = render_to_info(hass, '{{ "conversation" | exposed_entities }}')
    assert_result_info(info, [entry1.entity_id, entry2.entity_id])
    assert info.rate_limit is None


async def test_exposed_entities_multiple_assistants(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test exposed_entities with multiple assistants."""
    assert await async_setup_component(hass, "homeassistant", {})

    entry1 = entity_registry.async_get_or_create("light", "test", "entity1")
    entry2 = entity_registry.async_get_or_create("switch", "test", "entity2")
    entry3 = entity_registry.async_get_or_create("binary_sensor", "test", "entity3")

    # Expose different entities to different assistants
    async_expose_entity(hass, "conversation", entry1.entity_id, True)
    async_expose_entity(hass, "conversation", entry2.entity_id, True)

    async_expose_entity(hass, "cloud.alexa", entry2.entity_id, True)
    async_expose_entity(hass, "cloud.alexa", entry3.entity_id, True)

    # Test conversation assistant
    info = render_to_info(hass, '{{ exposed_entities("conversation") }}')
    assert_result_info(info, [entry1.entity_id, entry2.entity_id])
    assert info.rate_limit is None

    # Test Alexa assistant
    info = render_to_info(hass, '{{ exposed_entities("cloud.alexa") }}')
    assert_result_info(info, [entry2.entity_id, entry3.entity_id])
    assert info.rate_limit is None
