"""
Support for sous-vide machines.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/sousvide
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_CURRENT_TEMPERATURE, ATTR_ENTITY_ID, ATTR_MAX_TEMP,
    ATTR_MEASUREMENT_PRECISION, ATTR_MIN_TEMP, ATTR_OPERATION_MODE,
    ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT, SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_HEAT, STATE_OFF)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp

LOGGER = logging.getLogger(__name__)
DOMAIN = 'sous_vide'
GROUP_NAME_SOUS_VIDE = 'all sous-vide cookers'
SCAN_INTERVAL = timedelta(seconds=15)

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})
SET_TEMPERATURE_SCHEMA = SERVICE_SCHEMA.extend({
    vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
})

SERVICE_TO_METHOD = {
    SERVICE_TURN_ON: {'method': 'turn_on'},
    SERVICE_TURN_OFF: {'method': 'turn_off'},
    SERVICE_SET_TEMPERATURE: {'method': 'set_temp',
                              'schema': SET_TEMPERATURE_SCHEMA},
}


def setup(hass, config):
    """Perform setup for the component."""
    component = EntityComponent(
        LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_SOUS_VIDE)
    component.setup(config)

    def handle_sous_vide_service(service):
        """Callback for handling service invocations."""
        method = SERVICE_TO_METHOD[service.service]
        target_sous_vide_machines = component.async_extract_from_service(
            service)
        params = service.data.copy()
        params.pop(ATTR_ENTITY_ID, None)

        for sous_vide_machine in target_sous_vide_machines:
            getattr(sous_vide_machine, method["method"])(**params)
            hass.async_add_job(sous_vide_machine.async_update_ha_state)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service].get('schema', SERVICE_SCHEMA)
        hass.services.register(
            DOMAIN, service, handle_sous_vide_service, schema=schema)

    return True


class SousVideEntity(ToggleEntity):
    """Representation of a sous-vide device."""

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:oil-temperature'

    @property
    def precision(self):
        """Return the precision of the device's measurements."""

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the device."""

    @property
    def current_temperature(self) -> float:
        """Return the device's current temperature."""

    @property
    def target_temperature(self) -> float:
        """Return the device's target temperature."""

    @property
    def min_temperature(self) -> float:
        """Return the device's minimum temperature."""

    @property
    def max_temperature(self) -> float:
        """Return the device's maximum temperature."""

    @property
    def state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_CURRENT_TEMPERATURE: show_temp(
                self.hass, self.current_temperature, self.unit_of_measurement,
                self.precision),
            ATTR_MIN_TEMP: show_temp(
                self.hass, self.min_temperature, self.unit_of_measurement,
                self.precision),
            ATTR_MAX_TEMP: show_temp(
                self.hass, self.max_temperature, self.unit_of_measurement,
                self.precision),
            ATTR_TEMPERATURE: show_temp(
                self.hass, self.target_temperature, self.unit_of_measurement,
                self.precision),
            ATTR_UNIT_OF_MEASUREMENT: self.unit_of_measurement,
            ATTR_MEASUREMENT_PRECISION: self.precision,
            ATTR_OPERATION_MODE:
                STATE_OFF if self.state == STATE_OFF else STATE_HEAT,
        }

    def set_temp(self, temperature=None) -> None:
        """Set the target temperature of the device."""
        raise NotImplementedError()
