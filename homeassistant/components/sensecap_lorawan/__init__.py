"""Support SenseCAP devices over LoRaWAN."""

from lorawan_connection import ConnectionUnavailable
from sensecap_lorawan import SenseCapDevice, SenseCapDeviceCollection

from homeassistant.components.lorawan import DeviceManager
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import SenseCapCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
type SenseCapConfigEntry = ConfigEntry[
    DeviceManager[SenseCapDevice, SenseCapCoordinator]
]
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SenseCapConfigEntry) -> None:
    """Set up SenseCAP devices across the available LoRaWAN connections."""
    manager = entry.runtime_data = DeviceManager(
        hass,
        entry,
        create_collection=SenseCapDeviceCollection,
        create_coordinator=SenseCapCoordinator,
    )
    entry.async_on_unload(manager.close)
    try:
        await manager.async_setup()
    except ConnectionUnavailable as err:
        raise ConfigEntryNotReady(str(err)) from err
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SenseCapConfigEntry) -> None:
    """Unload entities; the manager releases the collection and coordinators."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
