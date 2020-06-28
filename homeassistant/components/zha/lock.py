"""Locks on Zigbee Home Automation networks."""
import functools
import logging

from zigpy.zcl.foundation import Status

from homeassistant.components.lock import (
    DOMAIN,
    STATE_LOCKED,
    STATE_UNLOCKED,
    LockEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .core import discovery
from .core.const import (
    CHANNEL_DOORLOCK,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)

""" The first state is Zigbee 'Not fully locked' """

STATE_LIST = [STATE_UNLOCKED, STATE_LOCKED, STATE_UNLOCKED]
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)

VALUE_TO_STATE = dict(enumerate(STATE_LIST))


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation Door Lock from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


@STRICT_MATCH(channel_names=CHANNEL_DOORLOCK)
class ZhaDoorLock(ZhaEntity, LockEntity):
    """Representation of a ZHA lock."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._doorlock_channel = self.cluster_channels.get(CHANNEL_DOORLOCK)

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._doorlock_channel, SIGNAL_ATTR_UPDATED, self.async_set_state
        )

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = VALUE_TO_STATE.get(last_state.state, last_state.state)

    @property
    def is_locked(self) -> bool:
        """Return true if entity is locked."""
        if self._state is None:
            return False
        return self._state == STATE_LOCKED

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return self.state_attributes

    async def async_lock(self, **kwargs):
        """Lock the lock."""
        result = await self._doorlock_channel.lock_door()
        if not isinstance(result, list) or result[0] is not Status.SUCCESS:
            self.error("Error with lock_door: %s", result)
            return
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlock the lock."""
        result = await self._doorlock_channel.unlock_door()
        if not isinstance(result, list) or result[0] is not Status.SUCCESS:
            self.error("Error with unlock_door: %s", result)
            return
        self.async_write_ha_state()

    async def async_update(self):
        """Attempt to retrieve state from the lock."""
        await super().async_update()
        await self.async_get_state()

    @callback
    def async_set_state(self, attr_id, attr_name, value):
        """Handle state update from channel."""
        self._state = VALUE_TO_STATE.get(value, self._state)
        self.async_write_ha_state()

    async def async_get_state(self, from_cache=True):
        """Attempt to retrieve state from the lock."""
        if self._doorlock_channel:
            state = await self._doorlock_channel.get_attribute_value(
                "lock_state", from_cache=from_cache
            )
            if state is not None:
                self._state = VALUE_TO_STATE.get(state, self._state)

    async def refresh(self, time):
        """Call async_get_state at an interval."""
        await self.async_get_state(from_cache=False)
