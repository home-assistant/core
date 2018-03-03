"""
Component to interface with various sensors that can be monitored.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/
"""

import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE,
    ATTR_ENTITY_ID)
from homeassistant.components import group

SENSOR_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'sensor'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

GROUP_NAME_ALL_SENSORS = 'all sensors'
ENTITY_ID_ALL_SENSORS = group.ENTITY_ID_FORMAT.format('all_sensors')

SCAN_INTERVAL = timedelta(seconds=30)


@bind_hass
def is_on(hass, entity_id=None):
    """Return if the sensor is on based on the statemachine.

    Async friendly.
    """
    entity_id = entity_id or ENTITY_ID_ALL_SENSORS
    return hass.states.is_state(entity_id, STATE_ON)


@bind_hass
def turn_on(hass, entity_id=None):
    """Turn all or specified sensor on."""
    hass.add_job(async_turn_on, hass, entity_id)


@callback
@bind_hass
def async_turn_on(hass, entity_id=None):
    """Turn all or specified sensor on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data))


@bind_hass
def turn_off(hass, entity_id=None):
    """Turn all or specified sensor off."""
    hass.add_job(async_turn_off, hass, entity_id)


@callback
@bind_hass
def async_turn_off(hass, entity_id=None):
    """Turn all or specified sensor off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.async_add_job(
        hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data))


@bind_hass
def toggle(hass, entity_id=None):
    """Toggle all or specified sensor."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


async def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_SENSORS)
    await component.async_setup(config)

    async def async_handle_sensor_service(service):
        """Handle calls to the sensor services."""
        target_sensors = component.async_extract_from_service(service)

        update_tasks = []
        for sensor in target_sensors:
            if service.service == SERVICE_TURN_ON:
                await sensor.async_turn_on()
            elif service.service == SERVICE_TOGGLE:
                await sensor.async_toggle()
            else:
                await sensor.async_turn_off()

            if not sensor.should_poll:
                continue
            update_tasks.append(sensor.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_TURN_OFF, async_handle_sensor_service,
        schema=SENSOR_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, async_handle_sensor_service,
        schema=SENSOR_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, async_handle_sensor_service,
        schema=SENSOR_SERVICE_SCHEMA)

    return True
