"""Tests for the ESPHome helpers of Connectivity Monitor."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.connectivity_monitor.esphome import (
    async_get_esphome_device_active,
    async_get_esphome_devices,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

ESPHOME_DOMAIN = "esphome"


def _create_esphome_config_entry(
    hass: HomeAssistant, entry_id: str = "esphome_entry_1", title: str = "ESP Node"
) -> MockConfigEntry:
    """Register and return an ESPHome MockConfigEntry."""
    entry = MockConfigEntry(
        domain=ESPHOME_DOMAIN,
        title=title,
        entry_id=entry_id,
        unique_id=f"mac_{entry_id}",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    return entry


# ──────────────────────────────────────────────────────────────────────────────
# async_get_esphome_devices — primary path (config entries)
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_esphome_devices_empty(hass: HomeAssistant) -> None:
    """Returns empty list when no ESPHome entries and no registry devices."""
    devices = await async_get_esphome_devices(hass)
    assert devices == []


async def test_get_esphome_devices_primary_path(hass: HomeAssistant) -> None:
    """Returns device info via the config-entry primary path."""
    entry = _create_esphome_config_entry(hass)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(ESPHOME_DOMAIN, "esp_id_001")},
        connections={("mac", "aa:bb:cc:dd:ee:ff")},
        name="ESP Node",
        manufacturer="Espressif",
        model="ESP32",
        sw_version="2024.1.0",
    )

    devices = await async_get_esphome_devices(hass)

    assert len(devices) == 1
    dev = devices[0]
    assert dev["entry_id"] == entry.entry_id
    assert dev["esphome_identifier"] == "esp_id_001"
    assert dev["esphome_mac"] == "aa:bb:cc:dd:ee:ff"
    assert dev["name"] == "ESP Node"
    assert dev["manufacturer"] == "Espressif"
    assert dev["model"] == "ESP32"


async def test_get_esphome_devices_skips_unloaded_entry(hass: HomeAssistant) -> None:
    """Config entries that are not LOADED are skipped in the primary path.

    The fallback identifier scan still picks the device up, but entry_id will be None.
    """
    entry = MockConfigEntry(
        domain=ESPHOME_DOMAIN,
        title="Unloaded",
        entry_id="unloaded_entry",
        unique_id="mac_unloaded",
        state=ConfigEntryState.NOT_LOADED,
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(ESPHOME_DOMAIN, "esp_unloaded")},
        name="Unloaded ESP",
    )

    devices = await async_get_esphome_devices(hass)
    # Device is returned via fallback path (entry_id is None)
    assert len(devices) == 1
    assert devices[0]["entry_id"] is None


async def test_get_esphome_devices_no_device_for_entry(hass: HomeAssistant) -> None:
    """Entry with no associated device is skipped gracefully."""
    _create_esphome_config_entry(hass, entry_id="no_device_entry")
    devices = await async_get_esphome_devices(hass)
    assert devices == []


async def test_get_esphome_devices_deduplication(hass: HomeAssistant) -> None:
    """Same device registry entry linked to two config entries is not doubled."""
    entry1 = _create_esphome_config_entry(hass, entry_id="e1", title="ESP-A")
    entry2 = _create_esphome_config_entry(hass, entry_id="e2", title="ESP-A-dup")

    device_registry = dr.async_get(hass)
    # Create device once; add second config entry to it
    dev = device_registry.async_get_or_create(
        config_entry_id=entry1.entry_id,
        identifiers={(ESPHOME_DOMAIN, "esp_dup")},
        name="Shared ESP",
    )
    device_registry.async_update_device(dev.id, add_config_entry_id=entry2.entry_id)

    devices = await async_get_esphome_devices(hass)
    # Should appear only once
    assert len(devices) == 1


async def test_get_esphome_devices_fallback_path(hass: HomeAssistant) -> None:
    """Falls back to device registry scan when config-entry primary path yields 0 devices."""
    # No config entries → primary finds nothing → fallback is used
    other_entry = MockConfigEntry(
        domain="other_domain",
        title="Other Entry",
        entry_id="some_other_entry",
    )
    other_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id="some_other_entry",
        identifiers={(ESPHOME_DOMAIN, "fallback_id")},
        connections={("mac", "11:22:33:44:55:66")},
        name="Fallback ESP",
    )

    devices = await async_get_esphome_devices(hass)

    assert len(devices) == 1
    assert devices[0]["esphome_identifier"] == "fallback_id"
    assert devices[0]["entry_id"] is None


async def test_get_esphome_devices_error(hass: HomeAssistant) -> None:
    """Returns empty list when device registry raises AttributeError."""
    with patch(
        "homeassistant.components.connectivity_monitor.esphome.dr.async_get",
        side_effect=AttributeError("boom"),
    ):
        devices = await async_get_esphome_devices(hass)
    assert devices == []


# ──────────────────────────────────────────────────────────────────────────────
# async_get_esphome_device_active
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_esphome_device_active_no_device(hass: HomeAssistant) -> None:
    """Returns None when the device is not in registry."""
    result = await async_get_esphome_device_active(hass, "nonexistent_device_id")
    assert result is None


async def test_get_esphome_device_active_no_entities(hass: HomeAssistant) -> None:
    """Returns None when device has no enabled ESPHome entities."""
    entry = _create_esphome_config_entry(hass)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(ESPHOME_DOMAIN, "no_entity_esp")},
        name="No Entity ESP",
    )

    result = await async_get_esphome_device_active(hass, entry.entry_id)
    assert result is None


async def test_get_esphome_device_active_active(hass: HomeAssistant) -> None:
    """Returns True when at least one entity is in a non-unavailable state."""
    entry = _create_esphome_config_entry(hass)

    device_registry = dr.async_get(hass)
    dev_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(ESPHOME_DOMAIN, "active_esp")},
        name="Active ESP",
    )

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        ESPHOME_DOMAIN,
        "active_esp_sensor",
        config_entry=entry,
        device_id=dev_entry.id,
    )

    # Set the entity state to something active
    hass.states.async_set(entity_entry.entity_id, "on")

    result = await async_get_esphome_device_active(hass, entry.entry_id)
    assert result is True


async def test_get_esphome_device_active_all_unavailable(hass: HomeAssistant) -> None:
    """Returns False when all ESPHome entities are unavailable."""
    entry = _create_esphome_config_entry(hass)

    device_registry = dr.async_get(hass)
    dev_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(ESPHOME_DOMAIN, "unavail_esp")},
        name="Unavail ESP",
    )

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        ESPHOME_DOMAIN,
        "unavail_esp_sensor",
        config_entry=entry,
        device_id=dev_entry.id,
    )

    hass.states.async_set(entity_entry.entity_id, "unavailable")

    result = await async_get_esphome_device_active(hass, entry.entry_id)
    assert result is False


async def test_get_esphome_device_active_fallback_identifier(
    hass: HomeAssistant,
) -> None:
    """Falls back to identifier-based lookup when device_id is not an entry_id."""
    # Create a device without a matching config entry
    fallback_entry = MockConfigEntry(
        domain=ESPHOME_DOMAIN,
        title="Fallback MAC ESP entry",
        entry_id="some_config_entry",
        state=ConfigEntryState.LOADED,
    )
    fallback_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    dev_entry = device_registry.async_get_or_create(
        config_entry_id="some_config_entry",
        identifiers={(ESPHOME_DOMAIN, "fallback_mac_001")},
        name="Fallback MAC ESP",
    )

    # Simulate that no ESPHome config entry with this id exists
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        ESPHOME_DOMAIN,
        "fallback_sensor",
        device_id=dev_entry.id,
    )
    hass.states.async_set(entity_entry.entity_id, "50")

    result = await async_get_esphome_device_active(hass, "fallback_mac_001")
    assert result is True


async def test_get_esphome_device_active_entity_no_state(hass: HomeAssistant) -> None:
    """Entity with no state object does not count as active."""
    entry = _create_esphome_config_entry(hass, entry_id="no_state_entry")

    device_registry = dr.async_get(hass)
    dev_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(ESPHOME_DOMAIN, "no_state_esp")},
        name="No State ESP",
    )

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        ESPHOME_DOMAIN,
        "no_state_sensor",
        config_entry=entry,
        device_id=dev_entry.id,
    )
    # Deliberately do NOT set a state for this entity

    result = await async_get_esphome_device_active(hass, entry.entry_id)
    assert result is False


async def test_get_esphome_device_active_error(hass: HomeAssistant) -> None:
    """Returns None on AttributeError."""
    with patch(
        "homeassistant.components.connectivity_monitor.esphome.dr.async_get",
        side_effect=AttributeError("boom"),
    ):
        result = await async_get_esphome_device_active(hass, "entry_id")
    assert result is None
