"""Tests for the Matter helpers of Connectivity Monitor."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.connectivity_monitor.matter import (
    async_get_matter_device_active,
    async_get_matter_devices,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

MATTER_DOMAIN = "matter"


# ──────────────────────────────────────────────────────────────────────────────
# async_get_matter_devices
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_matter_devices_empty(hass: HomeAssistant) -> None:
    """Returns empty list when no Matter devices are in the registry."""
    devices = await async_get_matter_devices(hass)
    assert devices == []


async def test_get_matter_devices_single(hass: HomeAssistant) -> None:
    """Returns device info for a single Matter device."""
    matter_entry = MockConfigEntry(
        domain=MATTER_DOMAIN,
        title="Matter Node 1",
        entry_id="matter_entry_1",
    )
    matter_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=matter_entry.entry_id,
        identifiers={(MATTER_DOMAIN, "1-5")},
        name="Bulb 1",
        manufacturer="ACME",
        model="AB100",
    )

    devices = await async_get_matter_devices(hass)

    assert len(devices) == 1
    dev = devices[0]
    assert dev["node_id"] == "1-5"
    assert dev["name"] == "Bulb 1"
    assert dev["manufacturer"] == "ACME"
    assert dev["model"] == "AB100"
    assert dev["device_id"] == device_entry.id


async def test_get_matter_devices_name_by_user_priority(hass: HomeAssistant) -> None:
    """name_by_user is preferred over auto-generated device name."""
    matter_entry2 = MockConfigEntry(
        domain=MATTER_DOMAIN,
        title="Matter Node 2",
        entry_id="matter_entry_2",
    )
    matter_entry2.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    dev = device_registry.async_get_or_create(
        config_entry_id=matter_entry2.entry_id,
        identifiers={(MATTER_DOMAIN, "1-6")},
        name="Auto Name",
    )
    device_registry.async_update_device(dev.id, name_by_user="Custom Name")

    devices = await async_get_matter_devices(hass)

    assert len(devices) == 1
    assert devices[0]["name"] == "Custom Name"


async def test_get_matter_devices_multiple(hass: HomeAssistant) -> None:
    """Returns multiple Matter devices."""
    device_registry = dr.async_get(hass)
    for i in range(3):
        e = MockConfigEntry(
            domain=MATTER_DOMAIN,
            title=f"Matter Node {i}",
            entry_id=f"matter_entry_{i}",
        )
        e.add_to_hass(hass)
        device_registry.async_get_or_create(
            config_entry_id=e.entry_id,
            identifiers={(MATTER_DOMAIN, f"1-{i}")},
            name=f"Device {i}",
        )

    devices = await async_get_matter_devices(hass)
    assert len(devices) == 3


async def test_get_matter_devices_non_matter_device_ignored(
    hass: HomeAssistant,
) -> None:
    """Device with non-matter identifier is not included."""
    other_entry = MockConfigEntry(
        domain="zha",
        title="ZHA Entry",
        entry_id="other_entry",
    )
    other_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("zha", "00:11:22:33:44:55")},
        name="Zigbee Device",
    )

    devices = await async_get_matter_devices(hass)
    assert devices == []


async def test_get_matter_devices_error(hass: HomeAssistant) -> None:
    """Returns empty list when registry raises AttributeError."""
    with patch(
        "homeassistant.components.connectivity_monitor.matter.dr.async_get",
        side_effect=AttributeError("boom"),
    ):
        devices = await async_get_matter_devices(hass)
    assert devices == []


async def test_get_matter_devices_node_id_fallback_name(hass: HomeAssistant) -> None:
    """Falls back to node_id when device has no name."""
    matter_entry_noname = MockConfigEntry(
        domain=MATTER_DOMAIN,
        title="Matter Node NN",
        entry_id="matter_entry_noname",
    )
    matter_entry_noname.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    dev = device_registry.async_get_or_create(
        config_entry_id=matter_entry_noname.entry_id,
        identifiers={(MATTER_DOMAIN, "2-10")},
    )
    # Ensure no name
    device_registry.async_update_device(dev.id, name=None, name_by_user=None)

    devices = await async_get_matter_devices(hass)
    assert len(devices) == 1
    assert devices[0]["name"] == "2-10"


# ──────────────────────────────────────────────────────────────────────────────
# async_get_matter_device_active
# ──────────────────────────────────────────────────────────────────────────────


async def test_get_matter_device_active_not_found(hass: HomeAssistant) -> None:
    """Returns None when the device is not in the registry."""
    result = await async_get_matter_device_active(hass, "9-99")
    assert result is None


async def test_get_matter_device_active_no_entities(hass: HomeAssistant) -> None:
    """Returns None when device has no enabled Matter entities."""
    matter_a1_entry = MockConfigEntry(
        domain=MATTER_DOMAIN,
        title="Matter Node A1",
        entry_id="matter_a1",
    )
    matter_a1_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=matter_a1_entry.entry_id,
        identifiers={(MATTER_DOMAIN, "3-1")},
        name="Empty Matter Device",
    )

    result = await async_get_matter_device_active(hass, "3-1")
    assert result is None


async def test_get_matter_device_active_active(hass: HomeAssistant) -> None:
    """Returns True when at least one entity is not unavailable."""
    device_registry = dr.async_get(hass)
    matter_entry = MockConfigEntry(
        domain=MATTER_DOMAIN,
        title="Matter Node",
        entry_id="matter_entry_active",
    )
    matter_entry.add_to_hass(hass)

    dev_entry = device_registry.async_get_or_create(
        config_entry_id=matter_entry.entry_id,
        identifiers={(MATTER_DOMAIN, "3-2")},
        name="Active Matter",
    )

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        MATTER_DOMAIN,
        "matter_active_sensor",
        config_entry=matter_entry,
        device_id=dev_entry.id,
    )
    hass.states.async_set(entity_entry.entity_id, "on")

    result = await async_get_matter_device_active(hass, "3-2")
    assert result is True


async def test_get_matter_device_active_all_unavailable(hass: HomeAssistant) -> None:
    """Returns False when all Matter entities are unavailable."""
    device_registry = dr.async_get(hass)
    matter_entry = MockConfigEntry(
        domain=MATTER_DOMAIN,
        title="Matter Node Unavail",
        entry_id="matter_entry_unavail",
    )
    matter_entry.add_to_hass(hass)

    dev_entry = device_registry.async_get_or_create(
        config_entry_id=matter_entry.entry_id,
        identifiers={(MATTER_DOMAIN, "3-3")},
        name="Unavail Matter",
    )

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        MATTER_DOMAIN,
        "matter_unavail_sensor",
        config_entry=matter_entry,
        device_id=dev_entry.id,
    )
    hass.states.async_set(entity_entry.entity_id, "unavailable")

    result = await async_get_matter_device_active(hass, "3-3")
    assert result is False


async def test_get_matter_device_active_entity_no_state(hass: HomeAssistant) -> None:
    """Returns False when entity exists but state object is missing."""
    device_registry = dr.async_get(hass)
    matter_entry = MockConfigEntry(
        domain=MATTER_DOMAIN,
        title="Matter Node NS",
        entry_id="matter_entry_ns",
    )
    matter_entry.add_to_hass(hass)

    dev_entry = device_registry.async_get_or_create(
        config_entry_id=matter_entry.entry_id,
        identifiers={(MATTER_DOMAIN, "3-4")},
        name="No State Matter",
    )

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        MATTER_DOMAIN,
        "matter_ns_sensor",
        config_entry=matter_entry,
        device_id=dev_entry.id,
    )
    # Do NOT set state

    result = await async_get_matter_device_active(hass, "3-4")
    assert result is False


async def test_get_matter_device_active_error(hass: HomeAssistant) -> None:
    """Returns None on AttributeError."""
    with patch(
        "homeassistant.components.connectivity_monitor.matter.dr.async_get",
        side_effect=AttributeError("boom"),
    ):
        result = await async_get_matter_device_active(hass, "3-5")
    assert result is None
