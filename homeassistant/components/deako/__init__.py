"""The deako integration."""

from pydeako import Deako, DeakoDiscoverer, FindDevicesError

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

PLATFORMS: list[Platform] = [Platform.LIGHT]

type DeakoConfigEntry = ConfigEntry[Deako]


async def async_setup_entry(hass: HomeAssistant, entry: DeakoConfigEntry) -> None:
    """Set up deako."""
    _zc = await zeroconf.async_get_instance(hass)
    discoverer = DeakoDiscoverer(_zc)

    connection = Deako(discoverer.get_address)

    await connection.connect()
    try:
        await connection.find_devices()
    except FindDevicesError as exc:
        await connection.disconnect()
        raise ConfigEntryNotReady(exc) from exc

    # If deako devices are advertising on mdns, we should be
    # able to get at least one device
    devices = connection.get_devices()
    if len(devices) == 0:
        await connection.disconnect()
        raise ConfigEntryNotReady(devices)

    entry.runtime_data = connection

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: DeakoConfigEntry) -> None:
    """Unload a config entry."""
    await entry.runtime_data.disconnect()

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
