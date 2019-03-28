"""
Platform for the Somfy MyLink device supporting the Synergy JsonRPC API.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.somfy_mylink/
"""
import logging

from homeassistant.components.cover import (ATTR_POSITION, SUPPORT_CLOSE,
                                            SUPPORT_OPEN, SUPPORT_SET_POSITION,
                                            SUPPORT_STOP, CoverDevice)
from . import DATA_SOMFY_MYLINK, CONF_DEFAULT_REVERSE
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
        if config_options.get(CONF_DEFAULT_REVERSE):
            cover_config['reverse'] = True
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

    def __init__(self, somfy_mylink, target_id='AABBCC', name='SomfyShade',
                 reverse=False, device_class='window'):
        """Initialize the cover."""
        self.somfy_mylink = somfy_mylink
        self._target_id = target_id
        self._name = name
        self._reverse = reverse
        self._device_class = device_class
        self._closed = False
        self._state = None
        self._state_ts = None
        self._supported_features = DEFAULT_SUPPORTED_FEATURES

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name
    
    @property
    def is_closed(self):
        """Return if the cover is closed."""
        pass

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if self._state is not None:
            return
        state = await super().async_get_last_state()
        if state:
            self._state = state.state
            self._state_ts = state.last_updated

    async def async_open_cover(self, **kwargs):
        """Wrap Homeassistant calls to open the cover."""
        if not self._reverse:
            await self.somfy_mylink.move_up(self._target_id)
        else:
            await self.somfy_mylink.move_down(self._target_id)

    async def async_close_cover(self, **kwargs):
        """Wrap Homeassistant calls to close the cover."""
        if not self._reverse:
            await self.somfy_mylink.move_down(self._target_id)
        else:
            await self.somfy_mylink.move_up(self._target_id)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.somfy_mylink.move_stop(self._target_id)
