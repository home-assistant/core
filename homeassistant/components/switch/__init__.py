"""
Component to interface with various switches that can be controlled remotely.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/switch/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.core import callback
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
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

_LOGGER = logging.getLogger(__name__)


@bind_hass
def is_on(hass, entity_id=None):
    """Return if the switch is on based on the statemachine.

    Async friendly.
    """
    entity_id = entity_id or ENTITY_ID_ALL_SWITCHES
    return hass.states.is_state(entity_id, STATE_ON)


@bind_hass
def turn_on(hass, entity_id=None):
    """Turn all or specified switch on."""
    hass.add_job(async_turn_on, hass, entity_id)


@callback
@bind_hass
def async_turn_on(hass, entity_id=None):
    """Turn all or specified switch on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data))


@bind_hass
def turn_off(hass, entity_id=None):
    """Turn all or specified switch off."""
    hass.add_job(async_turn_off, hass, entity_id)


@callback
@bind_hass
def async_turn_off(hass, entity_id=None):
    """Turn all or specified switch off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data))


@bind_hass
def toggle(hass, entity_id=None):
    """Toggle all or specified switch."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for switches."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_SWITCHES)
    yield from component.async_setup(config)

    @asyncio.coroutine
    def async_handle_switch_service(service):
        """Handle calls to the switch services."""
        target_switches = component.async_extract_from_service(service)

        update_tasks = []
        for switch in target_switches:
            if service.service == SERVICE_TURN_ON:
                yield from switch.async_turn_on()
            elif service.service == SERVICE_TOGGLE:
                yield from switch.async_toggle()
            else:
                yield from switch.async_turn_off()

            if not switch.should_poll:
                continue
            update_tasks.append(switch.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_TURN_OFF, async_handle_switch_service,
        schema=SWITCH_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, async_handle_switch_service,
        schema=SWITCH_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, async_handle_switch_service,
        schema=SWITCH_SERVICE_SCHEMA)

    return True


class SwitchDevice(ToggleEntity):
    """Representation of a switch."""

    # pylint: disable=no-self-use
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
