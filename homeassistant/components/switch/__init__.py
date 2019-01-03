"""
Component to interface with various switches that can be controlled remotely.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/switch/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.loader import bind_hass
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE,
    ATTR_ENTITY_ID)
from homeassistant.components import group

DOMAIN = 'switch'
DEPENDENCIES = ['group']
SCAN_INTERVAL = timedelta(seconds=30)

GROUP_NAME_ALL_SWITCHES = 'all switches'
ENTITY_ID_ALL_SWITCHES = group.ENTITY_ID_FORMAT.format('all_switches')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_TODAY_ENERGY_KWH = "today_energy_kwh"
ATTR_CURRENT_POWER_W = "current_power_w"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

PROP_TO_ATTR = {
    'current_power_w': ATTR_CURRENT_POWER_W,
    'today_energy_kwh': ATTR_TODAY_ENERGY_KWH,
}

SWITCH_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
})

_LOGGER = logging.getLogger(__name__)


@bind_hass
def is_on(hass, entity_id=None):
    """Return if the switch is on based on the statemachine.

    Async friendly.
    """
    entity_id = entity_id or ENTITY_ID_ALL_SWITCHES
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass, config):
    """Track states and offer events for switches."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_SWITCHES)
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_OFF, SWITCH_SERVICE_SCHEMA,
        'async_turn_off'
    )

    component.async_register_entity_service(
        SERVICE_TURN_ON, SWITCH_SERVICE_SCHEMA,
        'async_turn_on'
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE, SWITCH_SERVICE_SCHEMA,
        'async_toggle'
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class SwitchDevice(ToggleEntity):
    """Representation of a switch."""

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return None

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return None

    @property
    def is_standby(self):
        """Return true if device is in standby."""
        return None

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value:
                data[attr] = value

        return data
