"""Support for the ZHA platform."""
from __future__ import annotations

import functools
import time

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CLUSTER_HANDLER_POWER_CONFIGURATION,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity
from .sensor import Battery

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, Platform.DEVICE_TRACKER)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation device tracker from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.DEVICE_TRACKER]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


@STRICT_MATCH(cluster_handler_names=CLUSTER_HANDLER_POWER_CONFIGURATION)
class ZHADeviceScannerEntity(ScannerEntity, ZhaEntity):
    """Represent a tracked device."""

    _attr_should_poll = True  # BaseZhaEntity defaults to False
    _attr_name: str = "Device scanner"

    def __init__(self, unique_id, zha_device, cluster_handlers, **kwargs):
        """Initialize the ZHA device tracker."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._battery_cluster_handler = self.cluster_handlers.get(
            CLUSTER_HANDLER_POWER_CONFIGURATION
        )
        self._connected = False
        self._keepalive_interval = 60
        self._battery_level = None

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        if self._battery_cluster_handler:
            self.async_accept_signal(
                self._battery_cluster_handler,
                SIGNAL_ATTR_UPDATED,
                self.async_battery_percentage_remaining_updated,
            )

    async def async_update(self) -> None:
        """Handle polling."""
        if self.zha_device.last_seen is None:
            self._connected = False
        else:
            difference = time.time() - self.zha_device.last_seen
            if difference > self._keepalive_interval:
                self._connected = False
            else:
                self._connected = True

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self._connected

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.ROUTER

    @callback
    def async_battery_percentage_remaining_updated(self, attr_id, attr_name, value):
        """Handle tracking."""
        if attr_name != "battery_percentage_remaining":
            return
        self.debug("battery_percentage_remaining updated: %s", value)
        self._connected = True
        self._battery_level = Battery.formatter(value)
        self.async_write_ha_state()

    @property
    def battery_level(self):
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return self._battery_level

    @property  # type: ignore[misc]
    def device_info(  # pylint: disable=overridden-final-method
        self,
    ) -> DeviceInfo:
        """Return device info."""
        # We opt ZHA device tracker back into overriding this method because
        # it doesn't track IP-based devices.
        # Call Super because ScannerEntity overrode it.
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return ZhaEntity.device_info.fget(self)  # type: ignore[attr-defined]

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        # Call Super because ScannerEntity overrode it.
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        return ZhaEntity.unique_id.fget(self)  # type: ignore[attr-defined]
