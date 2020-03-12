"""Support for ZHA covers."""
from datetime import timedelta
import functools
import logging

from zigpy.zcl.foundation import Status

from homeassistant.components.cover import ATTR_POSITION, DOMAIN, CoverDevice
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .core import discovery
from .core.const import (
    CHANNEL_COVER,
    DATA_ZHA,
    DATA_ZHA_DISPATCHERS,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)
STRICT_MATCH = functools.partial(ZHA_ENTITIES.strict_match, DOMAIN)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Zigbee Home Automation cover from config entry."""
    entities_to_create = hass.data[DATA_ZHA][DOMAIN] = []

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS].append(unsub)


@STRICT_MATCH(channel_names=CHANNEL_COVER)
class ZhaCover(ZhaEntity, CoverDevice):
    """Representation of a ZHA cover."""

    def __init__(self, unique_id, zha_device, channels, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._cover_channel = self.cluster_channels.get(CHANNEL_COVER)
        self._current_position = None

    async def async_added_to_hass(self):
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        await self.async_accept_signal(
            self._cover_channel, SIGNAL_ATTR_UPDATED, self.async_set_position
        )

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state
        if "current_position" in last_state.attributes:
            self._current_position = last_state.attributes["current_position"]

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self.current_cover_position is None:
            return None
        return self.current_cover_position == 0

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._state == STATE_OPENING

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._state == STATE_CLOSING

    @property
    def current_cover_position(self):
        """Return the current position of ZHA cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._current_position

    @callback
    def async_set_position(self, attr_id, attr_name, value):
        """Handle position update from channel."""
        _LOGGER.debug("setting position: %s", value)
        self._current_position = 100 - value
        if self._current_position == 0:
            self._state = STATE_CLOSED
        elif self._current_position == 100:
            self._state = STATE_OPEN
        self.async_write_ha_state()

    @callback
    def async_update_state(self, state):
        """Handle state update from channel."""
        _LOGGER.debug("state=%s", state)
        self._state = state
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the window cover."""
        res = await self._cover_channel.up_open()
        if isinstance(res, list) and res[1] is Status.SUCCESS:
            self.async_update_state(STATE_OPENING)

    async def async_close_cover(self, **kwargs):
        """Close the window cover."""
        res = await self._cover_channel.down_close()
        if isinstance(res, list) and res[1] is Status.SUCCESS:
            self.async_update_state(STATE_CLOSING)

    async def async_set_cover_position(self, **kwargs):
        """Move the roller shutter to a specific position."""
        new_pos = kwargs[ATTR_POSITION]
        res = await self._cover_channel.go_to_lift_percentage(100 - new_pos)
        if isinstance(res, list) and res[1] is Status.SUCCESS:
            self.async_update_state(
                STATE_CLOSING if new_pos < self._current_position else STATE_OPENING
            )

    async def async_stop_cover(self, **kwargs):
        """Stop the window cover."""
        res = await self._cover_channel.stop()
        if isinstance(res, list) and res[1] is Status.SUCCESS:
            self._state = STATE_OPEN if self._current_position > 0 else STATE_CLOSED
            self.async_write_ha_state()

    async def async_update(self):
        """Attempt to retrieve the open/close state of the cover."""
        await super().async_update()
        await self.async_get_state()

    async def async_get_state(self, from_cache=True):
        """Fetch the current state."""
        _LOGGER.debug("polling current state")
        if self._cover_channel:
            pos = await self._cover_channel.get_attribute_value(
                "current_position_lift_percentage", from_cache=from_cache
            )
            _LOGGER.debug("read pos=%s", pos)

            if pos is not None:
                self._current_position = 100 - pos
                self._state = (
                    STATE_OPEN if self.current_cover_position > 0 else STATE_CLOSED
                )
            else:
                self._current_position = None
                self._state = None
