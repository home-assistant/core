"""Support for switching devices via Pilight to on and off."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import CONF_SWITCHES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import SWITCHES_SCHEMA, PilightBaseDevice

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): vol.Schema({cv.string: SWITCHES_SCHEMA})}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Pilight platform."""
    switches = config[CONF_SWITCHES]
    devices = []

    for dev_name, dev_config in switches.items():
        devices.append(PilightSwitch(hass, dev_name, dev_config))

    add_entities(devices)


class PilightSwitch(PilightBaseDevice, SwitchEntity):
    """Representation of a Pilight switch."""
