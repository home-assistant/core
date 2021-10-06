"""Support for scanning a network with nmap."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    CONF_SCAN_INTERVAL,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EXCLUDE, CONF_HOSTS
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from . import NmapDevice, NmapDeviceScanner, short_hostname, signal_device_update
from .const import (
    CONF_HOME_INTERVAL,
    CONF_OPTIONS,
    DEFAULT_OPTIONS,
    DOMAIN,
    TRACKER_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOSTS): cv.ensure_list,
        vol.Required(CONF_HOME_INTERVAL, default=0): cv.positive_int,
        vol.Required(
            CONF_CONSIDER_HOME, default=DEFAULT_CONSIDER_HOME.total_seconds()
        ): cv.time_period,
        vol.Optional(CONF_EXCLUDE, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_OPTIONS, default=DEFAULT_OPTIONS): cv.string,
    }
)


async def async_get_scanner(hass: HomeAssistant, config: ConfigType) -> None:
    """Validate the configuration and return a Nmap scanner."""
    validated_config = config[DEVICE_TRACKER_DOMAIN]

    if CONF_SCAN_INTERVAL in validated_config:
        scan_interval = validated_config[CONF_SCAN_INTERVAL].total_seconds()
    else:
        scan_interval = TRACKER_SCAN_INTERVAL

    if CONF_CONSIDER_HOME in validated_config:
        consider_home = validated_config[CONF_CONSIDER_HOME].total_seconds()
    else:
        consider_home = DEFAULT_CONSIDER_HOME.total_seconds()

    import_config = {
        CONF_HOSTS: ",".join(validated_config[CONF_HOSTS]),
        CONF_HOME_INTERVAL: validated_config[CONF_HOME_INTERVAL],
        CONF_CONSIDER_HOME: consider_home,
        CONF_EXCLUDE: ",".join(validated_config[CONF_EXCLUDE]),
        CONF_OPTIONS: validated_config[CONF_OPTIONS],
        CONF_SCAN_INTERVAL: scan_interval,
    }

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=import_config,
        )
    )

    _LOGGER.warning(
        "Your Nmap Tracker configuration has been imported into the UI, "
        "please remove it from configuration.yaml. "
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up device tracker for Nmap Tracker component."""
    nmap_tracker = hass.data[DOMAIN][entry.entry_id]

    @callback
    def device_new(mac_address):
        """Signal a new device."""
        async_add_entities([NmapTrackerEntity(nmap_tracker, mac_address, True)])

    @callback
    def device_missing(mac_address):
        """Signal a missing device."""
        async_add_entities([NmapTrackerEntity(nmap_tracker, mac_address, False)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, nmap_tracker.signal_device_new, device_new)
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, nmap_tracker.signal_device_missing, device_missing
        )
    )


class NmapTrackerEntity(ScannerEntity):
    """An Nmap Tracker entity."""

    def __init__(
        self, nmap_tracker: NmapDeviceScanner, mac_address: str, active: bool
    ) -> None:
        """Initialize an nmap tracker entity."""
        self._mac_address = mac_address
        self._nmap_tracker = nmap_tracker
        self._tracked = self._nmap_tracker.devices.tracked
        self._active = active

    @property
    def _device(self) -> NmapDevice:
        """Get latest device state."""
        return self._tracked[self._mac_address]

    @property
    def is_connected(self) -> bool:
        """Return device status."""
        return self._active

    @property
    def name(self) -> str:
        """Return device name."""
        return self._device.name

    @property
    def unique_id(self) -> str:
        """Return device unique id."""
        return self._mac_address

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._device.ipv4

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac_address

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        if not self._device.hostname:
            return None
        return short_hostname(self._device.hostname)

    @property
    def source_type(self) -> str:
        """Return tracker source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self._mac_address)},
            "default_manufacturer": self._device.manufacturer,
            "default_name": self.name,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def icon(self) -> str:
        """Return device icon."""
        return "mdi:lan-connect" if self._active else "mdi:lan-disconnect"

    @callback
    def async_process_update(self, online: bool) -> None:
        """Update device."""
        self._active = online

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return {
            "last_time_reachable": self._device.last_update.isoformat(
                timespec="seconds"
            ),
            "reason": self._device.reason,
        }

    @callback
    def async_on_demand_update(self, online: bool) -> None:
        """Update state."""
        self.async_process_update(online)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_device_update(self._mac_address),
                self.async_on_demand_update,
            )
        )
