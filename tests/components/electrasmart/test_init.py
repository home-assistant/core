"""Tests for the Electra Smart integration setup."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.electrasmart.const import DOMAIN
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_device_registry(
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    setup_integration: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "a8032ab12345"), config_entry.entry_id
    )
    assert device_entry == snapshot
