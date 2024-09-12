"""Tests for iNELS integration."""

from unittest.mock import Mock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import inels
from .conftest import setup_inels_test_integration


async def test_remove_devices_with_no_entities(hass: HomeAssistant, mock_mqtt) -> None:
    """Test that devices with no entities are removed."""
    await setup_inels_test_integration(hass)

    config_entry = next(
        entry
        for entry in hass.config_entries.async_entries(inels.DOMAIN)
        if entry.domain == inels.DOMAIN
    )

    hass.data.setdefault(inels.DOMAIN, {})

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(inels.DOMAIN, "device_1")},
        name="Device_with_entity",
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(inels.DOMAIN, "device_2")},
        name="Device_to_be_removed",
    )

    # Add an entity for device_1 but not for device_2
    entity_registry.async_get_or_create(
        domain="sensor",
        platform=inels.DOMAIN,
        unique_id="entity_1",
        config_entry=config_entry,
        device_id=device_1.id,
    )

    with patch.object(
        device_registry, "async_remove_device", new_callable=Mock
    ) as mock_remove_device:
        await inels.async_remove_devices_with_no_entities(hass, config_entry)

        assert mock_remove_device.call_count == 1
        mock_remove_device.assert_called_with(device_id=device_2.id)


async def test_remove_old_entities(hass: HomeAssistant) -> None:
    """Test that old entities are removed."""
    await setup_inels_test_integration(hass)

    config_entry = next(
        entry
        for entry in hass.config_entries.async_entries(inels.DOMAIN)
        if entry.domain == inels.DOMAIN
    )

    hass.data.setdefault(inels.DOMAIN, {})
    hass.data[inels.DOMAIN][config_entry.entry_id] = {
        inels.OLD_ENTITIES: {
            "sensor": ["sensor.old_entity_1"],
            "light": ["light.old_entity_2"],
        }
    }

    entity_registry = er.async_get(hass)

    # Add old entities to the entity registry
    entity_registry.async_get_or_create(
        domain="sensor",
        platform=inels.DOMAIN,
        unique_id="old_entity_1",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        domain="light",
        platform=inels.DOMAIN,
        unique_id="old_entity_2",
        config_entry=config_entry,
    )

    with patch.object(
        entity_registry, "async_remove", new_callable=Mock
    ) as mock_remove_entity:
        await inels.async_remove_old_entities(hass, config_entry)

        # Ensure all pending tasks are completed
        await hass.async_block_till_done()

        # Verify that old entities were removed
        assert mock_remove_entity.call_count == 2
        mock_remove_entity.assert_any_call("sensor.old_entity_1")
        mock_remove_entity.assert_any_call("light.old_entity_2")
