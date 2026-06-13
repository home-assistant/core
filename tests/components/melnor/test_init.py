"""Test the Melnor integration setup."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.melnor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    FAKE_ADDRESS_1,
    mock_config_entry,
    patch_async_ble_device_from_address,
    patch_async_register_callback,
    patch_melnor_device,
)


async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the Bluetooth connection."""
    entry = mock_config_entry(hass)

    with (
        patch_async_ble_device_from_address(),
        patch_melnor_device(),
        patch_async_register_callback(),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, FAKE_ADDRESS_1)}
    )
    assert device_entry == snapshot
