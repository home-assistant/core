"""Test the Enigma2 integration init."""

from unittest.mock import patch

from homeassistant.components.enigma2.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import TEST_REQUIRED, MockDevice

from tests.common import MockConfigEntry


async def test_device_without_mac_address(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that a device gets successfully registered when the device doesn't report a MAC address."""
    mock_device = MockDevice()
    mock_device.mac_address = None
    with patch(
        "homeassistant.components.enigma2.coordinator.OpenWebIfDevice.__new__",
        return_value=mock_device,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN, data=TEST_REQUIRED, title="name", unique_id="123456"
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert device_registry.async_get_device({(DOMAIN, entry.unique_id)}) is not None


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    with patch(
        "homeassistant.components.enigma2.coordinator.OpenWebIfDevice.__new__",
        return_value=MockDevice(),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=TEST_REQUIRED, title="name")
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
