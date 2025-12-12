"""Tests for the Compit device registry."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.compit.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_device_registry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    device_entries = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )

    assert device_entries == snapshot


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device info for individual devices."""
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "1")})
    assert device_entry is not None
    assert device_entry == snapshot(name="device_1")

    device_entry_2 = device_registry.async_get_device(identifiers={(DOMAIN, "2")})
    assert device_entry_2 is not None
    assert device_entry_2 == snapshot(name="device_2")


async def test_device_cleanup_on_coordinator_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that devices are updated when coordinator updates."""
    # Get initial device count
    initial_devices = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    initial_count = len(initial_devices)

    assert initial_count > 0

    # Force coordinator refresh to ensure devices are still present
    coordinator = init_integration.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify device count remains the same after refresh
    updated_devices = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    assert len(updated_devices) == initial_count
