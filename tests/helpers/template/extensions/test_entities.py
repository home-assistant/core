"""Test entity functions for Home Assistant templates."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry
from tests.helpers.template.helpers import render


def test_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entity_name method."""
    assert render(hass, "{{ entity_name('sensor.fake') }}") is None

    entry = entity_registry.async_get_or_create(
        "sensor", "test", "unique_1", original_name="Registry Sensor"
    )
    assert render(hass, f"{{{{ entity_name('{entry.entity_id}') }}}}") == (
        "Registry Sensor"
    )
    assert render(hass, f"{{{{ '{entry.entity_id}' | entity_name }}}}") == (
        "Registry Sensor"
    )

    entity_registry.async_update_entity(entry.entity_id, name="My Custom Sensor")
    assert render(hass, f"{{{{ entity_name('{entry.entity_id}') }}}}") == (
        "My Custom Sensor"
    )

    # Falls back to state for entities not in the registry
    hass.states.async_set(
        "light.no_unique_id", "on", {"friendly_name": "No Unique ID Light"}
    )
    assert render(hass, "{{ entity_name('light.no_unique_id') }}") == (
        "No Unique ID Light"
    )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        name="My Device",
    )
    entry2 = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_2",
        config_entry=config_entry,
        device_id=device_entry.id,
        has_entity_name=True,
        original_name="Temperature",
    )
    assert render(hass, f"{{{{ entity_name('{entry2.entity_id}') }}}}") == (
        "Temperature"
    )

    # Strips device name prefix
    entity_registry.async_update_entity(
        entry2.entity_id, name="My Device Custom Sensor"
    )
    assert render(hass, f"{{{{ entity_name('{entry2.entity_id}') }}}}") == (
        "Custom Sensor"
    )


def test_is_hidden_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test is_hidden_entity method."""
    hidden_entity = entity_registry.async_get_or_create(
        "sensor", "mock", "hidden", hidden_by=er.RegistryEntryHider.USER
    )
    visible_entity = entity_registry.async_get_or_create("sensor", "mock", "visible")
    assert render(hass, f"{{{{ is_hidden_entity('{hidden_entity.entity_id}') }}}}")

    assert not render(hass, f"{{{{ is_hidden_entity('{visible_entity.entity_id}') }}}}")

    assert not render(
        hass,
        f"{{{{ ['{visible_entity.entity_id}'] | select('is_hidden_entity') | first }}}}",
    )
