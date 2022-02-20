"""Support for tracking the online status of a UPS."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, KEY_STATUS, VALUE_ONLINE

DEFAULT_NAME = "UPS Online Status"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up an APCUPSd Online Status binary sensor."""
    apcups_data = hass.data[DOMAIN]

    add_entities([OnlineStatus(config, apcups_data)], True)


class OnlineStatus(BinarySensorEntity):
    """Representation of an UPS online status."""

    def __init__(self, config, data):
        """Initialize the APCUPSd binary device."""
        self._data = data
        self._attr_name = config[CONF_NAME]

    def update(self):
        """Get the status report from APCUPSd and set this entity's state."""
        self._attr_is_on = int(self._data.status[KEY_STATUS], 16) & VALUE_ONLINE > 0
