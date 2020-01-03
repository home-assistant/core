"""Support for the ZHA platform."""
import functools
import logging
import time

from homeassistant.components.device_tracker import DOMAIN, SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .core.const import (
    CHANNEL_POWER_CONFIGURATION,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ATTR_UPDATED,
    ZHA_DISCOVERY_NEW,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity
from .sensor import Battery

STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation device tracker from config entry."""

    async def async_discover(discovery_info):
        await _async_setup_entities(
            hass, config_entry, async_add_entities, [discovery_info]
        )

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    device_trackers = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if device_trackers is not None:
        await _async_setup_entities(
            hass, config_entry, async_add_entities, device_trackers.values()
        )
        del hass.data[DATA_ZHA][DOMAIN]


async def _async_setup_entities(
    hass, config_entry, async_add_entities, discovery_infos
):
    """Set up the ZHA device trackers."""
    entities = []
    for discovery_info in discovery_infos:
        zha_dev = discovery_info["zha_device"]
        channels = discovery_info["channels"]

        entity = ZHA_ENTITIES.get_entity(
            DOMAIN, zha_dev, channels, ZHADeviceScannerEntity
        )
        if entity:
            entities.append(entity(**discovery_info))

    if entities:
        async_add_entities(entities, update_before_add=True)


@STRICT_MATCH(channel_names=CHANNEL_POWER_CONFIGURATION)
class ZHADeviceScannerEntity(ScannerEntity, ZhaEntity):
    """Represent a tracked device."""

    def __init__(self, **kwargs):
        """Initialize the ZHA device tracker."""
        super().__init__(**kwargs)
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
