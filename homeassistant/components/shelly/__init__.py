"""The Shelly integration."""
import asyncio
from datetime import timedelta
import logging

from aiocoap import error as aiocoap_error
import aioshelly
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, update_coordinator
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN

PLATFORMS = ["switch"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Shelly component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Shelly from a config entry."""
    try:
        async with async_timeout.timeout(5):
            device = await aioshelly.Device.create(
                entry.data["host"], aiohttp_client.async_get_clientsession(hass)
            )
    except asyncio.TimeoutError:
        raise ConfigEntryNotReady

    wrapper = hass.data[DOMAIN][entry.entry_id] = ShellyDeviceWrapper(
        hass, entry, device
    )

    wrapper.async_setup()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


class ShellyDeviceWrapper(update_coordinator.DataUpdateCoordinator):
    """Wrapper for a Shelly device with Home Assistant specific functions."""

    def __init__(self, hass, entry, device: aioshelly.Device):
        """Initialize the Shelly device wrapper."""
        super().__init__(
            hass,
            _LOGGER,
            name=device.settings["name"] or entry.title,
            update_interval=timedelta(seconds=5),
        )
        self.hass = hass
        self.entry = entry
        self.device = device
        self._unsub_stop = None

    async def _async_update_data(self):
        """Fetch data."""
        try:
            async with async_timeout.timeout(5):
                return await self.device.update()
        except aiocoap_error.Error:
            raise update_coordinator.UpdateFailed("Error fetching data")

    @property
    def mac(self):
        """Mac address of the device."""
        return self.device.settings["device"]["mac"]

    @property
    def device_info(self):
        """Entity device info."""
        return {
            "name": self.name or self.entry.title,
            "connections": {(CONNECTION_NETWORK_MAC, self.mac)},
            "manufacturer": "Shelly",
            "model": self.device.settings["device"]["type"],
            "sw_version": self.device.settings["fw"],
        }

    @callback
    def async_setup(self):
        """Set up the wrapper."""
        self._unsub_stop = self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop
        )

    async def shutdown(self):
        """Shutdown the device wrapper."""
        await self.device.shutdown()
        if self._unsub_stop:
            self._unsub_stop()
            self._unsub_stop = None

    async def _handle_ha_stop(self, _):
        """Handle Home Assistant stopping."""
        self._unsub_stop = None
        await self.shutdown()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        await hass.data[DOMAIN].pop(entry.entry_id).shutdown()

    return unload_ok
