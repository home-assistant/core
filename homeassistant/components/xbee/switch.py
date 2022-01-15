"""Support for XBee Zigbee switches."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PLATFORM_SCHEMA, XBeeDigitalOut, XBeeDigitalOutConfig
from .const import CONF_ON_STATE, DOMAIN, STATES

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_ON_STATE): vol.In(STATES)})


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the XBee Zigbee switch platform."""
    zigbee_device = hass.data[DOMAIN]
    add_entities([XBeeSwitch(XBeeDigitalOutConfig(config), zigbee_device)])


class XBeeSwitch(XBeeDigitalOut, SwitchEntity):
    """Representation of a XBee Zigbee Digital Out device."""
