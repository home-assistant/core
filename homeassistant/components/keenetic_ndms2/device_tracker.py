"""Support for Keenetic routers as device tracker."""
from datetime import timedelta
import logging
from typing import List, Optional, Set

from ndms2_client import Device
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_SCHEMA,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.dt as dt_util

from .const import (
    CONF_CONSIDER_HOME,
    CONF_INTERFACES,
    CONF_LEGACY_INTERFACE,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_INTERFACE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TELNET_PORT,
    DOMAIN,
    ROUTER,
)
from .router import KeeneticRouter

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = DEVICE_TRACKER_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_TELNET_PORT): cv.port,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_LEGACY_INTERFACE, default=DEFAULT_INTERFACE): cv.string,
    }
)


async def async_get_scanner(hass: HomeAssistant, config):
    """Import legacy configuration from YAML."""

    scanner_config = config[DEVICE_TRACKER_DOMAIN]
    scan_interval: Optional[timedelta] = scanner_config.get(CONF_SCAN_INTERVAL)
    consider_home: Optional[timedelta] = scanner_config.get(CONF_CONSIDER_HOME)

    host: str = scanner_config[CONF_HOST]
    hass.data[DOMAIN][f"imported_options_{host}"] = {
        CONF_INTERFACES: [scanner_config[CONF_LEGACY_INTERFACE]],
        CONF_SCAN_INTERVAL: int(scan_interval.total_seconds())
        if scan_interval
        else DEFAULT_SCAN_INTERVAL,
        CONF_CONSIDER_HOME: int(consider_home.total_seconds())
        if consider_home
        else DEFAULT_CONSIDER_HOME,
    }

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: scanner_config[CONF_HOST],
                CONF_PORT: scanner_config[CONF_PORT],
                CONF_USERNAME: scanner_config[CONF_USERNAME],
                CONF_PASSWORD: scanner_config[CONF_PASSWORD],
            },
        )
    )

    _LOGGER.warning(
        "Your Keenetic NDMS2 configuration has been imported into the UI, "
        "please remove it from configuration.yaml. "
        "Loading Keenetic NDMS2 via scanner setup is now deprecated"
    )

    return None


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up device tracker for Keenetic NDMS2 component."""
    router: KeeneticRouter = hass.data[DOMAIN][config_entry.entry_id][ROUTER]

    tracked = set()

    @callback
    def update_from_router():
        """Update the status of devices."""
        update_items(router, async_add_entities, tracked)

    update_from_router()

    registry = await entity_registry.async_get_registry(hass)
    # Restore devices that are not a part of active clients list.
    restored = []
    for entity_entry in registry.entities.values():
        if (
            entity_entry.config_entry_id == config_entry.entry_id
            and entity_entry.domain == DEVICE_TRACKER_DOMAIN
        ):
            mac = entity_entry.unique_id.partition("_")[0]
            if mac not in tracked:
                tracked.add(mac)
                restored.append(
                    KeeneticTracker(
                        Device(
                            mac=mac,
                            # restore the original name as set by the router before
                            name=entity_entry.original_name,
                            ip=None,
                            interface=None,
                        ),
                        router,
                    )
                )

    if restored:
        async_add_entities(restored)

    async_dispatcher_connect(hass, router.signal_update, update_from_router)


@callback
def update_items(router: KeeneticRouter, async_add_entities, tracked: Set[str]):
    """Update tracked device state from the hub."""
    new_tracked: List[KeeneticTracker] = []
    for mac, device in router.last_devices.items():
        if mac not in tracked:
            tracked.add(mac)
            new_tracked.append(KeeneticTracker(device, router))

    if new_tracked:
        async_add_entities(new_tracked)


class KeeneticTracker(ScannerEntity):
    """Representation of network device."""

    def __init__(self, device: Device, router: KeeneticRouter):
        """Initialize the tracked device."""
        self._device = device
        self._router = router
        self._last_seen = (
            dt_util.utcnow() if device.mac in router.last_devices else None
        )

    @property
    def should_poll(self) -> bool:
        """Return False since entity pushes its state to HA."""
        return False

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return (
            self._last_seen
            and (dt_util.utcnow() - self._last_seen)
            < self._router.consider_home_interval
        )

    @property
    def source_type(self):
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name or self._device.mac

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{self._device.mac}_{self._router.config_entry.entry_id}"

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._device.ip if self.is_connected else None

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device.mac

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self._router.available

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self.is_connected:
            return {
                "interface": self._device.interface,
            }
        return None

    @property
    def device_info(self):
        """Return a client description for device registry."""
        info = {
            "connections": {(CONNECTION_NETWORK_MAC, self._device.mac)},
            "identifiers": {(DOMAIN, self._device.mac)},
        }

        if self._device.name:
            info["name"] = self._device.name

        return info

    async def async_added_to_hass(self):
        """Client entity created."""
        _LOGGER.debug("New network device tracker %s (%s)", self.name, self.unique_id)

        @callback
        def update_device():
            _LOGGER.debug(
                "Updating Keenetic tracked device %s (%s)",
                self.entity_id,
                self.unique_id,
            )
            new_device = self._router.last_devices.get(self._device.mac)
            if new_device:
                self._device = new_device
                self._last_seen = dt_util.utcnow()

            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._router.signal_update, update_device
            )
        )
