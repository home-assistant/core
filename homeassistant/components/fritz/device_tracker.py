"""Support for FRITZ!Box routers."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import ConfigType

from .common import FritzBoxTools
from .const import DATA_FRITZ, DEFAULT_DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

YAML_DEFAULT_HOST = "169.254.1.1"
YAML_DEFAULT_USERNAME = "admin"

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HOST),
    cv.deprecated(CONF_USERNAME),
    cv.deprecated(CONF_PASSWORD),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_HOST, default=YAML_DEFAULT_HOST): cv.string,
            vol.Optional(CONF_USERNAME, default=YAML_DEFAULT_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
        }
    ),
)


async def async_get_scanner(hass: HomeAssistant, config: ConfigType):
    """Import legacy FRITZ!Box configuration."""
    _LOGGER.debug("Import legacy FRITZ!Box configuration from YAML")

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DEVICE_TRACKER_DOMAIN],
        )
    )

    _LOGGER.warning(
        "Your Fritz configuration has been imported into the UI, "
        "please remove it from configuration.yaml. "
        "Loading Fritz via scanner setup is now deprecated"
    )

    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up device tracker for FRITZ!Box component."""
    _LOGGER.debug("Starting FRITZ!Box device tracker")
    router = hass.data[DOMAIN][entry.entry_id]
    data_fritz = hass.data[DATA_FRITZ]

    @callback
    def update_router():
        """Update the values of the router."""
        _async_add_entities(router, async_add_entities, data_fritz)

    async_dispatcher_connect(hass, router.signal_device_new, update_router)

    update_router()


@callback
def _async_add_entities(router, async_add_entities, data_fritz):
    """Add new tracker entities from the router."""

    def _is_tracked(mac, device):
        for tracked in data_fritz.tracked.values():
            if mac in tracked:
                return True

        return False

    new_tracked = []
    if router.unique_id not in data_fritz.tracked:
        data_fritz.tracked[router.unique_id] = set()

    for mac, device in router.devices.items():
        if device.ip_address == "" or _is_tracked(mac, device):
            continue

        new_tracked.append(FritzBoxTracker(router, device))
        data_fritz.tracked[router.unique_id].add(mac)

    if new_tracked:
        async_add_entities(new_tracked)


class FritzBoxTracker(ScannerEntity):
    """This class queries a FRITZ!Box router."""

    def __init__(self, router: FritzBoxTools, device):
        """Initialize a FRITZ!Box device."""
        self._router = router
        self._mac = device.mac_address
        self._name = device.hostname or DEFAULT_DEVICE_NAME
        self._active = False
        self._attrs: dict = {}

    @property
    def is_connected(self):
        """Return device status."""
        return self._active

    @property
    def name(self):
        """Return device name."""
        return self._name

    @property
    def unique_id(self):
        """Return device unique id."""
        return self._mac

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._router.devices[self._mac].ip_address

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac

    @property
    def hostname(self) -> str:
        """Return hostname of the device."""
        return self._router.devices[self._mac].hostname

    @property
    def source_type(self) -> str:
        """Return tracker source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def device_info(self):
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self._mac)},
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "AVM",
            "model": "FRITZ!Box Tracked device",
            "via_device": (
                DOMAIN,
                self._router.unique_id,
            ),
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return device icon."""
        if self.is_connected:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @callback
    def async_process_update(self) -> None:
        """Update device."""
        device = self._router.devices[self._mac]
        self._active = device.is_connected

        if device.last_activity:
            self._attrs["last_time_reachable"] = device.last_activity.isoformat(
                timespec="seconds"
            )

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self.async_process_update()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_process_update()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )
