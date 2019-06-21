import logging
import voluptuous as vol

from homeassistant.components.fan import (FanEntity, PLATFORM_SCHEMA,
                                          SUPPORT_SET_SPEED)
from homeassistant.const import (CONF_NAME, CONF_HOST, ATTR_ENTITY_ID)

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the VeSync fan platform"""
    
    if discovery_info is None:
        return

    fans = []

    manager = hass.data[DOMAIN]['manager']

    if isinstance(manager.fans, list) and manager.fans:
        if len(manager.outlets) == 1:
            count_string = 'fan'
        else:
            count_string = 'fans'

        _LOGGER.info("Discovered %d VeSync %s", len(manager.fans),
                     count_string)

        for fan in manager.fans:
            fans.append(VeSyncFanHA(fan))
            _LOGGER.info("Added a VeSync fan named '%s'", fan.device_name)
    else:
        _LOGGER.info("No VeSync fans found")
    
    add_entities(fans)


class VeSyncFanHA(FanEntity)