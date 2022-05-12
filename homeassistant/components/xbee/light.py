"""Support for XBee Zigbee lights."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import PLATFORM_SCHEMA, XBeeDigitalOut, XBeeDigitalOutConfig
from .const import CONF_ON_STATE, DEFAULT_ON_STATE, DOMAIN, STATES

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_ON_STATE, default=DEFAULT_ON_STATE): vol.In(STATES)}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create and add an entity based on the configuration."""
    zigbee_device = hass.data[DOMAIN]
    add_entities([XBeeLight(XBeeDigitalOutConfig(config), zigbee_device)])


class XBeeLight(XBeeDigitalOut, LightEntity):
    """Use XBeeDigitalOut as light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
