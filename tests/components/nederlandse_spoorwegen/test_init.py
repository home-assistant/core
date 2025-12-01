"""Test the Nederlandse Spoorwegen init."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_registry_integration(
    hass: HomeAssistant,
    mock_nsapi,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry integration creates correct devices."""
    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    # Get all devices created for this config entry
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    # Snapshot the devices to ensure they have the correct structure
    assert device_entries == snapshot
