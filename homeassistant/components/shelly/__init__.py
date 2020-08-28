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
from homeassistant.helpers import (
    aiohttp_client,
    device_registry,
    entity,
    update_coordinator,
)

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
    except (asyncio.TimeoutError, OSError) as err:
        raise ConfigEntryNotReady from err

    wrapper = hass.data[DOMAIN][entry.entry_id] = ShellyDeviceWrapper(
        hass, entry, device
    )
    await wrapper.async_setup()

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
        # Race condition on shutdown. Stop all the fetches.
        if self._unsub_stop is None:
            return None

        try:
            async with async_timeout.timeout(5):
                return await self.device.update()
        except aiocoap_error.Error as err:
            raise update_coordinator.UpdateFailed("Error fetching data") from err

    @property
    def model(self):
        """Model of the device."""
        return self.device.settings["device"]["type"]

    @property
    def mac(self):
        """Mac address of the device."""
        return self.device.settings["device"]["mac"]

    async def async_setup(self):
        """Set up the wrapper."""
        self._unsub_stop = self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop
        )
        dev_reg = await device_registry.async_get_registry(self.hass)
        model_type = self.device.settings["device"]["type"]
        dev_reg.async_get_or_create(
            config_entry_id=self.entry.entry_id,
            name=self.name,
            connections={(device_registry.CONNECTION_NETWORK_MAC, self.mac)},
            # This is duplicate but otherwise via_device can't work
            identifiers={(DOMAIN, self.mac)},
            manufacturer="Shelly",
            model=aioshelly.MODEL_NAMES.get(model_type, model_type),
            sw_version=self.device.settings["fw"],
        )

    async def shutdown(self):
        """Shutdown the device wrapper."""
        if self._unsub_stop:
            self._unsub_stop()
            self._unsub_stop = None
        await self.device.shutdown()

    async def _handle_ha_stop(self, _):
        """Handle Home Assistant stopping."""
        self._unsub_stop = None
        await self.shutdown()


class ShellyBlockEntity(entity.Entity):
    """Helper class to represent a block."""

    def __init__(self, wrapper: ShellyDeviceWrapper, block):
        """Initialize Shelly entity."""
        self.wrapper = wrapper
        self.block = block

    @property
    def name(self):
        """Name of entity."""
        return f"{self.wrapper.name} - {self.block.description}"

    @property
    def should_poll(self):
        """If device should be polled."""
        return False

    @property
    def device_info(self):
        """Device info."""
        return {
            "connections": {(device_registry.CONNECTION_NETWORK_MAC, self.wrapper.mac)}
        }

    @property
    def available(self):
        """Available."""
        return self.wrapper.last_update_success

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return f"{self.wrapper.mac}-{self.block.index}"

    async def async_added_to_hass(self):
        """When entity is added to HASS."""
        self.async_on_remove(self.wrapper.async_add_listener(self._update_callback))

    async def async_update(self):
        """Update entity with latest info."""
        await self.wrapper.async_request_refresh()

    @callback
    def _update_callback(self):
        """Handle device update."""
        self.async_write_ha_state()


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
