"""The Shelly integration."""
import asyncio
import logging
from socket import gethostbyname

import aioshelly
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry, update_coordinator

from .const import COAP_CONTEXT, DATA_CONFIG_ENTRY, DOMAIN

PLATFORMS = ["binary_sensor", "cover", "light", "sensor", "switch"]
_LOGGER = logging.getLogger(__name__)


async def get_coap_context(hass):
    """Init COAP context if not exists."""
    if DOMAIN not in hass.data:
        hass.data.setdefault(DOMAIN, {})
    if COAP_CONTEXT not in hass.data[DOMAIN]:
        hass.data[DOMAIN][COAP_CONTEXT] = aioshelly.COAP()
        await hass.data[DOMAIN][COAP_CONTEXT].initialize()

    async def shutdown_listener(*_):
        """Home Assistant shutdown listener."""
        hass.data[DOMAIN][COAP_CONTEXT].close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_listener)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Shelly component."""
    await get_coap_context(hass)
    hass.data[DOMAIN][DATA_CONFIG_ENTRY] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Shelly from a config entry."""
    temperature_unit = "C" if hass.config.units.is_metric else "F"
    options = aioshelly.ConnectionOptions(
        gethostbyname(entry.data[CONF_HOST]),
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
        temperature_unit,
    )

    coap_context = hass.data[DOMAIN][COAP_CONTEXT]

    try:
        async with async_timeout.timeout(5):
            device = await aioshelly.Device.create(
                aiohttp_client.async_get_clientsession(hass),
                coap_context,
                options,
            )
    except (asyncio.TimeoutError, OSError) as err:
        raise ConfigEntryNotReady from err

    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][
        entry.entry_id
    ] = ShellyDeviceWrapper(hass, entry, device)
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
            name=device.settings["name"] or device.settings["device"]["hostname"],
        )
        self.hass = hass
        self.entry = entry
        self.device = device
        self._update_from_multicast = False

        self.device.subscribe_updates(self._multicast_update)

    def _multicast_update(self, data):
        """Handle multicast device update."""
        self._update_from_multicast = True
        self.hass.async_create_task(self.async_refresh())

    async def _async_update_data(self):
        """Fetch data."""
        if self._update_from_multicast:
            self._update_from_multicast = False
            return

        try:
            async with async_timeout.timeout(5):
                return await self.device.update()
        except OSError as err:
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
        hass.data[DOMAIN][DATA_CONFIG_ENTRY].pop(entry.entry_id)

    return unload_ok
