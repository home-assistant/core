"""Support for the ZHA platform."""
import functools
import logging
import time
from typing import List, Tuple

from homeassistant.components.device_tracker import DOMAIN, SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .core import typing as zha_typing
from .core.const import (
    CHANNEL_POWER_CONFIGURATION,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    DATA_ZHA_PLATFORM_LOADED,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_ENQUEUE_ENTITY,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity
from .sensor import Battery

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation device tracker from config entry."""
    entities = []

    async def async_discover():
        """Add enqueued entities."""
        if not entities:
            return
        to_add = [ent(*args) for ent, args in entities]
        async_add_entities(to_add, update_before_add=True)
        entities.clear()

    def async_enqueue_entity(
        entity: zha_typing.CALLABLE_T, args: Tuple[str, zha_typing.ZhaDeviceType, List]
    ):
        """Stash entity for later addition."""
        entities.append((entity, args))

    unsub = async_dispatcher_connect(hass, SIGNAL_ADD_ENTITIES, async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)
    unsub = async_dispatcher_connect(
        hass, f"{SIGNAL_ENQUEUE_ENTITY}_{DOMAIN}", async_enqueue_entity
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)
    hass.data[DATA_ZHA][DATA_ZHA_PLATFORM_LOADED][DOMAIN].set()


@STRICT_MATCH(channel_names=CHANNEL_POWER_CONFIGURATION)
class ZHADeviceScannerEntity(ScannerEntity, ZhaEntity):
    """Represent a tracked device."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Initialize the ZHA device tracker."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._battery_channel = self.cluster_channels.get(CHANNEL_POWER_CONFIGURATION)
        self._connected = False
        self._keepalive_interval = 60
        self._should_poll = True
        self._battery_level = None

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        if self._battery_channel:
            await self.async_accept_signal(
                self._battery_channel,
                SIGNAL_ATTR_UPDATED,
                self.async_battery_percentage_remaining_updated,
            )

    async def async_update(self):
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
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_ROUTER

    @callback
    def async_battery_percentage_remaining_updated(self, value):
        """Handle tracking."""
        self.debug("battery_percentage_remaining updated: %s", value)
        self._connected = True
        self._battery_level = Battery.formatter(value)
        self.async_schedule_update_ha_state()

    @property
    def battery_level(self):
        """Return the battery level of the device.

        Percentage from 0-100.
        """
        return self._battery_level
