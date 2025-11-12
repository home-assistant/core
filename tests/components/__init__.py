"""The tests for components."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_device_registry


async def target_entities(hass: HomeAssistant, domain: str) -> None:
    """Create multiple entities associated with different targets."""
    await async_setup_component(hass, domain, {})

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    floor_reg = fr.async_get(hass)
    floor = floor_reg.async_create("Test Floor")

    area_reg = ar.async_get(hass)
    area = area_reg.async_create("Test Area", floor_id=floor.floor_id)

    label_reg = lr.async_get(hass)
    label = label_reg.async_create("Test Label")

    device = dr.DeviceEntry(id="test_device", area_id=area.id, labels={label.label_id})
    mock_device_registry(hass, {device.id: device})

    entity_reg = er.async_get(hass)
    # Entity associated with area
    entity_area = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_area",
        suggested_object_id=f"area_{domain}",
    )
    entity_reg.async_update_entity(entity_area.entity_id, area_id=area.id)

    # Entity associated with device
    entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_device",
        suggested_object_id=f"device_{domain}",
        device_id=device.id,
    )

    # Entity associated with label
    entity_label = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_label",
        suggested_object_id=f"label_{domain}",
    )
    entity_reg.async_update_entity(entity_label.entity_id, labels={label.label_id})

    # Return all available entities
    return [
        f"{domain}.standalone_{domain}",
        f"{domain}.label_{domain}",
        f"{domain}.area_{domain}",
        f"{domain}.device_{domain}",
    ]
