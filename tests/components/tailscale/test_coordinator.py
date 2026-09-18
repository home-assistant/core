"""Tests for the Tailscale coordinator."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_remove_stale_devices(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_tailscale: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that devices removed from Tailscale are removed from device registry."""
    # Verify initial devices exist (should be 3 from fixture)
    devices = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    assert len(devices) == 3

    # Store device IDs for later verification
    device_ids = [list(device.identifiers)[0][1] for device in devices]
    assert "123456" in device_ids
    assert "123457" in device_ids
    assert "123458" in device_ids

    # Simulate device removal in Tailscale (only device 123456 remains)
    # Get the original device data from the mock
    original_devices = mock_tailscale.devices.return_value
    mock_tailscale.devices.return_value = {"123456": original_devices["123456"]}

    # Trigger natural refresh by advancing time
    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    # Verify devices 123457 and 123458 were removed
    remaining_devices = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    assert len(remaining_devices) == 1

    remaining_device = remaining_devices[0]
    remaining_id = list(remaining_device.identifiers)[0][1]
    assert remaining_id == "123456"
    assert remaining_device.name == "frencks-iphone"


async def test_no_devices_removed_when_all_present(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that no devices are removed when all Tailscale devices still exist."""
    # Verify initial devices exist (should be 3 from fixture)
    initial_devices = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    assert len(initial_devices) == 3

    # Trigger natural refresh (devices unchanged)
    freezer.tick(timedelta(seconds=60))
    await hass.async_block_till_done()

    # Verify no devices were removed
    final_devices = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    assert len(final_devices) == 3
