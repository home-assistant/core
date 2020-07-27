"""Support for switching devices via Pilight to on and off."""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_SWITCHES
import homeassistant.helpers.config_validation as cv

from .base_class import SWITCHES_SCHEMA, PilightBaseDevice

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): vol.Schema({cv.string: SWITCHES_SCHEMA})}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Pilight platform."""
    switches = config.get(CONF_SWITCHES)
    devices = []

    for dev_name, dev_config in switches.items():
        devices.append(PilightSwitch(hass, dev_name, dev_config))

    add_entities(devices)


class PilightSwitch(PilightBaseDevice, SwitchEntity):
    """Representation of a Pilight switch."""
