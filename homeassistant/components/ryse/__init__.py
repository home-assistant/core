"""The RYSE integration."""

from ryseble.device import RyseBLEDevice

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

type RyseConfigEntry = ConfigEntry[RyseBLEDevice]

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: RyseConfigEntry) -> bool:
    """Set up RYSE."""
    address = entry.unique_id
    assert address is not None

    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find RYSE device with address {address}")

    device = RyseBLEDevice(address)
    entry.runtime_data = device

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RyseConfigEntry) -> bool:
    """Unload a RYSE config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
