"""
Platform for the Somfy MyLink device supporting the Synergy JsonRPC API.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.somfy_mylink/
"""
import logging

from homeassistant.components.cover import (ATTR_POSITION, SUPPORT_CLOSE,
                                            SUPPORT_OPEN, SUPPORT_SET_POSITION,
                                            SUPPORT_STOP, CoverDevice)
from homeassistant.components.somfy_mylink import DATA_SOMFY_MYLINK
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['somfy_mylink']
DEFAULT_SUPPORTED_FEATURES = (SUPPORT_OPEN | SUPPORT_STOP | SUPPORT_CLOSE)
ENTITY_ID_FORMAT = 'cover.{}'


async def async_setup_platform(hass,
                               config,
                               async_add_entities,
                               discovery_info=None):
    """Discover and configure Somfy covers."""
    if discovery_info is None:
        return
    somfy_mylink = hass.data[DATA_SOMFY_MYLINK]
    config_options = discovery_info
    cover_list = []
    mylink_status = await somfy_mylink.status_info()
    for cover in mylink_status['result']:
        cover_config = {}
        cover_config['target_id'] = cover['targetID']
        for key, val in config_options.get('default', {}).items():
            cover_config[key] = val
        for config_entity, config_opt in config_options.items():
            entity_id = ENTITY_ID_FORMAT.format(slugify(cover['name']))
            if config_entity == entity_id:
                for key, val in config_opt.items():
                    cover_config[key] = val
        cover_config['name'] = cover['name']
        cover_list.append(SomfyShade(somfy_mylink, **cover_config))
        _LOGGER.info('Adding Somfy Cover: %s with targetID %s',
                     cover_config['name'], cover_config['target_id'])
    async_add_entities(cover_list)


class SomfyShade(CoverDevice, RestoreEntity):
    """Object for controlling a Somfy cover."""

    LISTEN_INTERVAL = 1

    def __init__(self, somfy_mylink, target_id='AABBCC', name='SomfyShade',
                 move_time=None, reverse=False, device_class='window'):
        """Initialize the cover."""
        self.somfy_mylink = somfy_mylink
        self._target_id = target_id
        self._name = name
        self._move_time = move_time
        self._reverse = reverse
        self._device_class = device_class
        self._position = 0
        self._set_position = None
        self._requested_closing = True
        self._unsub_listener_cover = None
        self._partial_move_time = None
        self._is_opening = False
        self._is_closing = False
        self._closed = True
        self._state = None
        self._state_ts = None
        self._supported_features = DEFAULT_SUPPORTED_FEATURES
        if self._move_time:
            self._supported_features |= SUPPORT_SET_POSITION

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._closed

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._is_closing

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._is_opening

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        if self._move_time:
            return self._position

    async def mylink_open_cover(self):
        """Open the cover, respecting reversal status."""
        if not self._reverse:
            await self.somfy_mylink.move_up(self._target_id)
        else:
            await self.somfy_mylink.move_down(self._target_id)

    async def mylink_close_cover(self):
        """Close the cover, respecting reversal status."""
        if not self._reverse:
            await self.somfy_mylink.move_down(self._target_id)
        else:
            await self.somfy_mylink.move_up(self._target_id)

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        if self._state is not None:
            return
        state = await self.async_get_last_state()
        if state:
            self._state = state.state
            self._state_ts = state.last_updated
            if self._move_time:
                self._position = state.attributes.get('current_position', 0)
            else:
                self._position = None
            if state.state == 'closed':
                self._closed = True
            else:
                self._closed = False

    async def async_open_cover(self, **kwargs):
        """Handles Homeassistant calls to open the cover."""
        if self._move_time:
            await self.async_set_cover_position(position=100)
            self._closed = False
            return
        await self.mylink_open_cover()
        self._closed = None

    async def async_close_cover(self, **kwargs):
        """Handles Homeassistant calls to close the cover."""
        if self._move_time:
            await self.async_set_cover_position(position=0)
            self._closed = True
            return
        await self.mylink_close_cover()
        self._closed = None

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.somfy_mylink.move_stop(self._target_id)
        self._is_closing = False
        self._is_opening = False
        self._closed = None
        if self._position is None:
            return
        if self._unsub_listener_cover is not None:
            self._unsub_listener_cover()
            self._unsub_listener_cover = None
            self._set_position = None

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        self._set_position = round(position, -1)
        if self._position == position:
            return
        self._partial_move_time = self._calculate_move_time(self._set_position)
        self._requested_closing = position < self._position
        _LOGGER.debug("Moving to position %s in %s seconds",
                      self._set_position, self._partial_move_time)
        if self._requested_closing:
            await self.mylink_close_cover()
            if self._position is None:
                self._closed = True
                self._position = 100
        else:
            await self.mylink_open_cover()
            if self._position is None:
                self._closed = False
                self._position = 0
        self._listen_cover()

    def _calculate_move_time(self, target_position):
        """Calculate time required to move the cover."""
        current_pos = self._position
        move_time = self._move_time
        perc_time = move_time / 100
        position_diff = current_pos - target_position
        if position_diff > 0:
            total_move_time = (perc_time * position_diff)
        else:
            total_move_time = (perc_time * -position_diff)
        return total_move_time

    def _listen_cover(self):
        """Listen for changes in cover."""
        listen_interval_str = "/{}".format(self.LISTEN_INTERVAL)
        if self._unsub_listener_cover is None:
            self._unsub_listener_cover = async_track_time_change(
                self.hass, self._time_changed_cover,
                second=listen_interval_str)

    async def _time_changed_cover(self, now):
        """Track time changes."""
        move_increment = int((100/self._move_time)*self.LISTEN_INTERVAL)
        if self._requested_closing:
            self._position -= move_increment
        else:
            self._position += move_increment
        _LOGGER.debug("%s At position %s, incrementing to %s",
                      now, self._position, self._set_position)
        curr_position = round(self._position, -1)
        if curr_position == self._set_position:
            self._position = curr_position
            if curr_position in (100, 0):
                self._closed = curr_position == 0
                self._unsub_listener_cover()
                self._unsub_listener_cover = None
            else:
                await self.async_stop_cover()
        self._closed = self.current_cover_position <= 0
        self.async_schedule_update_ha_state()
