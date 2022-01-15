"""Support for Zigbee binary sensors."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PLATFORM_SCHEMA, XBeeDigitalIn, XBeeDigitalInConfig
from .const import CONF_ON_STATE, DOMAIN, STATES

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_ON_STATE): vol.In(STATES)})


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the XBee Zigbee binary sensor platform."""
    zigbee_device = hass.data[DOMAIN]
    add_entities([XBeeBinarySensor(XBeeDigitalInConfig(config), zigbee_device)], True)


class XBeeBinarySensor(XBeeDigitalIn, BinarySensorEntity):
    """Use XBeeDigitalIn as binary sensor."""
