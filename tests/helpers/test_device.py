"""Tests for the Device Utils."""

from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device import (
    async_device_info_to_link_from_device_id,
    async_device_info_to_link_from_entity,
    async_entity_id_to_device,
    async_entity_id_to_device_id,
    async_remove_stale_devices_links_keep_current_device,
    async_remove_stale_devices_links_keep_entity_device,
)

from tests.common import MockConfigEntry


async def test_entity_id_to_device_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test returning an entity's device / device ID."""
    config_entry = MockConfigEntry(domain="my")
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        identifiers={("test", "current_device")},
        connections={("mac", "30:31:32:33:34:00")},
        config_entry_id=config_entry.entry_id,
    )
    assert device is not None

    # Entity registry
    entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=config_entry,
        device_id=device.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    device_id = async_entity_id_to_device_id(
        hass,
        entity_id_or_uuid=entity.entity_id,
    )
    assert device_id == device.id
    assert (
        async_entity_id_to_device(
            hass,
            entity_id_or_uuid=entity.entity_id,
        )
        == device
    )

    assert (
        async_entity_id_to_device_id(
            hass,
            entity_id_or_uuid="unknown.entity_id",
        )
        is None
    )
    assert (
        async_entity_id_to_device(
            hass,
            entity_id_or_uuid="unknown.entity_id",
        )
        is None
    )

    device_id = async_entity_id_to_device_id(
        hass,
        entity_id_or_uuid=entity.id,
    )
    assert device_id == device.id
    assert (
        async_entity_id_to_device(
            hass,
            entity_id_or_uuid=entity.id,
        )
        == device
    )

    with pytest.raises(vol.Invalid):
        async_entity_id_to_device_id(
            hass,
            entity_id_or_uuid="unknown_uuid",
        )

    with pytest.raises(vol.Invalid):
        async_entity_id_to_device(
            hass,
            entity_id_or_uuid="unknown_uuid",
        )


async def test_device_info_to_link(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The link helpers are deprecated and always return None.

    A device_info carrying another device's identifiers implicitly added the caller's
    config entry to that device, which a single-config-entry device can't represent - it
    would silently fork a duplicate instead. Entities still attach to another config
    entry's device by setting entity.device_entry.
    """
    config_entry = MockConfigEntry(domain="my")
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        identifiers={("test", "my_device")},
        connections={("mac", "30:31:32:33:34:00")},
        config_entry_id=config_entry.entry_id,
    )

    # Source entity registry
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=config_entry,
        device_id=device.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    # No link device_info is returned, even for an existing entity and device
    with patch("homeassistant.helpers.device.report_usage") as report_usage:
        assert (
            async_device_info_to_link_from_entity(
                hass, entity_id_or_uuid=source_entity.entity_id
            )
            is None
        )
        assert (
            async_device_info_to_link_from_device_id(hass, device_id=device.id) is None
        )
    assert report_usage.call_count == 2

    # With a non-existent entity id
    assert (
        async_device_info_to_link_from_entity(hass, entity_id_or_uuid="sensor.invalid")
        is None
    )

    # With a non-existent device id
    assert async_device_info_to_link_from_device_id(hass, device_id="abcdefghi") is None

    # With a None device id
    assert async_device_info_to_link_from_device_id(hass, device_id=None) is None


async def test_remove_stale_devices_links_deprecated_noop(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The stale-device-link helpers are deprecated and do nothing.

    A device belongs to a single config entry, so a helper no longer adds its config
    entry to another device and there is no stale config entry link to remove. The
    helpers leave the devices and entities untouched and only report the deprecated
    usage; helpers set entity.device_entry and clean up devices with
    async_remove_helper_devices instead.
    """
    helper_config_entry = MockConfigEntry(domain="helper_integration")
    helper_config_entry.add_to_hass(hass)
    host_config_entry = MockConfigEntry(domain="host_integration")
    host_config_entry.add_to_hass(hass)

    # A device owned by another config entry, plus one owned by the helper config entry
    current_device = device_registry.async_get_or_create(
        identifiers={("test", "current_device")},
        config_entry_id=host_config_entry.entry_id,
    )
    stale_device = device_registry.async_get_or_create(
        identifiers={("test", "stale_device")},
        config_entry_id=helper_config_entry.entry_id,
    )
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "host_integration",
        "source",
        config_entry=host_config_entry,
        device_id=current_device.id,
    )
    # Helper entity left on a device owned by the helper config entry
    helper_entity = entity_registry.async_get_or_create(
        "sensor",
        "helper_integration",
        "helper",
        config_entry=helper_config_entry,
        device_id=stale_device.id,
    )

    with patch("homeassistant.helpers.device.report_usage") as report_usage:
        async_remove_stale_devices_links_keep_current_device(
            hass,
            entry_id=helper_config_entry.entry_id,
            current_device_id=current_device.id,
        )
        async_remove_stale_devices_links_keep_entity_device(
            hass,
            entry_id=helper_config_entry.entry_id,
            source_entity_id_or_uuid=source_entity.entity_id,
        )
    await hass.async_block_till_done()

    # Both helpers reported the deprecated usage and changed nothing
    assert report_usage.call_count == 2
    assert device_registry.async_get(current_device.id) is not None
    assert device_registry.async_get(stale_device.id) is not None
    helper_entity_entry = entity_registry.async_get(helper_entity.entity_id)
    assert helper_entity_entry.device_id == stale_device.id
