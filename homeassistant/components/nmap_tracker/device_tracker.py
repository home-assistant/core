"""Support for scanning a network with nmap."""

import logging
from typing import Callable

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import NmapDeviceScanner
from .const import CONF_HOME_INTERVAL, CONF_OPTIONS, DEFAULT_OPTIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOSTS): cv.ensure_list,
        vol.Required(CONF_HOME_INTERVAL, default=0): cv.positive_int,
        vol.Optional(CONF_EXCLUDE, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_OPTIONS, default=DEFAULT_OPTIONS): cv.string,
    }
)


def async_get_scanner(hass, config):
    """Validate the configuration and return a Nmap scanner."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DEVICE_TRACKER_DOMAIN],
        )
    )

    _LOGGER.warning(
        "Your Nmap Tracker configuration has been imported into the UI, "
        "please remove it from configuration.yaml. "
    )

    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up device tracker for Nmap Tracker component."""
    nmap_tracker = hass.data[DOMAIN][entry.entry_id]

    @callback
    def update_router(ipv4):
        """Update the values of the router."""
        async_add_entities([NmapTrackerEntity(nmap_tracker, ipv4)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, nmap_tracker.signal_device_new, update_router)
    )


class NmapTrackerEntity(ScannerEntity):
    """An Nmap Tracker entity."""

    def __init__(self, nmap_tracker: NmapDeviceScanner, ipv4: str) -> None:
        """Initialize an nmap tracker entity."""
        self._ipv4 = ipv4
        self._nmap_tracker = nmap_tracker
        self._tracked = self._nmap_tracker.devices.tracked
        self._device = self._tracked[ipv4]
        self._active = False

    @property
    def is_connected(self) -> bool:
        """Return device status."""
        return self._active

    @property
    def name(self) -> str:
        """Return device name."""
        return self._device.hostname

    @property
    def unique_id(self) -> str:
        """Return device unique id."""
        return self._device.mac_address

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._ipv4

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device.mac_address

    @property
    def hostname(self) -> str:
        """Return hostname of the device."""
        return self._device.hostname

    @property
    def source_type(self) -> str:
        """Return tracker source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def device_info(self):
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self._device.mac_address)},
            "name": self.name,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return device icon."""
        return "mdi:lan-connect" if self._active else "mdi:lan-disconnect"

    @callback
    def async_process_update(self, online: bool) -> None:
        """Update device."""
        self._active = online

    @property
    def extra_state_attributes(self):
        """Return the attributes."""
        return {
            "last_time_reachable": self._device.last_update.isoformat(timespec="seconds")
        }

    @callback
    def async_on_demand_update(self, online: bool):
        """Update state."""
        self.async_process_update(online)
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_process_update(True)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._nmap_tracker.signal_device_update(self._ipv4),
                self.async_on_demand_update,
            )
        )
