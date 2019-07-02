"""Support for the ZHA platform."""
import logging
import time
from homeassistant.components.device_tracker import (
    SOURCE_TYPE_ZIGBEE, DOMAIN
)
from homeassistant.components.device_tracker.config_entry import (
    TrackerEntity
)
from homeassistant.const import (
    STATE_NOT_HOME,
    STATE_HOME
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .core.const import (
    DATA_ZHA, DATA_ZHA_DISPATCHERS, ZHA_DISCOVERY_NEW,
    POWER_CONFIGURATION_CHANNEL, SIGNAL_STATE_ATTR,
    SIGNAL_ATTR_UPDATED
)
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation device tracker from config entry."""
    async def async_discover(discovery_info):
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    [discovery_info])

    unsub = async_dispatcher_connect(
        hass, ZHA_DISCOVERY_NEW.format(DOMAIN), async_discover)
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)

    device_trackers = hass.data.get(DATA_ZHA, {}).get(DOMAIN)
    if device_trackers is not None:
        await _async_setup_entities(hass, config_entry, async_add_entities,
                                    device_trackers.values())
        del hass.data[DATA_ZHA][DOMAIN]

    return True


async def _async_setup_entities(hass, config_entry, async_add_entities,
                                discovery_infos):
    """Set up the ZHA device trackers."""
    entities = []
    for discovery_info in discovery_infos:
        entities.append(ZHADeviceTrackerEntity(**discovery_info))

    async_add_entities(entities, update_before_add=True)


class ZHADeviceTrackerEntity(TrackerEntity, ZhaEntity):
    """Represent a tracked device."""

    def __init__(self, **kwargs):
        """Initialize the ZHA device tracker."""
        super().__init__(**kwargs)
        self._battery_channel = self.cluster_channels.get(
            POWER_CONFIGURATION_CHANNEL)
        self._last_seen = None
        self._seen = False
        self._keepalive_interval = 60
        self._should_poll = True

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        if self._battery_channel:
            await self.async_accept_signal(
                self._battery_channel, SIGNAL_STATE_ATTR,
                self.async_attribute_updated)
            await self.async_accept_signal(
                self._battery_channel, SIGNAL_ATTR_UPDATED,
                self.async_attribute_updated)

    async def async_update(self):
        """Handle polling."""
        if self._last_seen is None:
            self._seen = False
        else:
            difference = time.time() - self._last_seen
            if difference > self._keepalive_interval:
                self._seen = False
            else:
                self._seen = True

    @property
    def state(self):
        """Return the state of the device."""
        if self._seen:
            return STATE_HOME
        return STATE_NOT_HOME

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return None

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return None

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_ZIGBEE

    @callback
    def async_attribute_updated(self, attribute, value):
        """Handle tracking."""
        self._last_seen = time.time()
