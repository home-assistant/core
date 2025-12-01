"""Tests for the Fressnapf Tracker integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def snapshot_devices(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot device entries."""
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device_entries
    for device_entry in device_entries:
        assert device_entry == snapshot(name=f"{device_entry.name}-entry"), (
            f"device entry snapshot failed for {device_entry.name}"
        )
