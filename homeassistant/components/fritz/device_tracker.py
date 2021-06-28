"""Support for FRITZ!Box routers."""
from __future__ import annotations

import datetime
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .common import Device, FritzBoxTools, FritzData, FritzDevice
from .const import DATA_FRITZ, DEFAULT_DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

YAML_DEFAULT_HOST = "169.254.1.1"
YAML_DEFAULT_USERNAME = "admin"

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_HOST),
    cv.deprecated(CONF_USERNAME),
    cv.deprecated(CONF_PASSWORD),
    PARENT_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_HOST, default=YAML_DEFAULT_HOST): cv.string,
            vol.Optional(CONF_USERNAME, default=YAML_DEFAULT_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
        }
    ),
)


async def async_get_scanner(hass: HomeAssistant, config: ConfigType) -> None:
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
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for FRITZ!Box component."""
    _LOGGER.debug("Starting FRITZ!Box device tracker")
    router: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]
    data_fritz: FritzData = hass.data[DATA_FRITZ]

    @callback
    def update_router() -> None:
        """Update the values of the router."""
        _async_add_entities(router, async_add_entities, data_fritz)

    entry.async_on_unload(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )

    update_router()


@callback
def _async_add_entities(
    router: FritzBoxTools,
    async_add_entities: AddEntitiesCallback,
    data_fritz: FritzData,
) -> None:
    """Add new tracker entities from the router."""

    def _is_tracked(mac: str, device: Device) -> bool:
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

    def __init__(self, router: FritzBoxTools, device: FritzDevice) -> None:
        """Initialize a FRITZ!Box device."""
        self._router = router
        self._mac: str = device.mac_address
        self._name: str = device.hostname or DEFAULT_DEVICE_NAME
        self._last_activity: datetime.datetime | None = device.last_activity
        self._active = False

    @property
    def is_connected(self) -> bool:
        """Return device status."""
        return self._active

    @property
    def name(self) -> str:
        """Return device name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return device unique id."""
        return self._mac

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        if self._mac:
            return self._router.devices[self._mac].ip_address
        return None

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        if self._mac:
            return self._router.devices[self._mac].hostname
        return None

    @property
    def source_type(self) -> str:
        """Return tracker source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self._mac)},
            "identifiers": {(DOMAIN, self.unique_id)},
            "default_name": self.name,
            "default_manufacturer": "AVM",
            "default_model": "FRITZ!Box Tracked device",
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
    def icon(self) -> str:
        """Return device icon."""
        if self.is_connected:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        attrs: dict[str, str] = {}
        if self._last_activity is not None:
            attrs["last_time_reachable"] = self._last_activity.isoformat(
                timespec="seconds"
            )
        return attrs

    @callback
    def async_process_update(self) -> None:
        """Update device."""
        if not self._mac:
            return

        device = self._router.devices[self._mac]
        self._active = device.is_connected
        self._last_activity = device.last_activity

    @callback
    def async_on_demand_update(self) -> None:
        """Update state."""
        self.async_process_update()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_process_update()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )
