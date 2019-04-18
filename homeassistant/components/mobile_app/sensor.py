"""Sensor platform for mobile_app."""
from functools import partial

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (ATTR_CONFIG_ENTRY_ID, ATTR_SENSOR_STATE,
                    ATTR_SENSOR_TYPE_SENSOR as ENTITY_TYPE,
                    ATTR_SENSOR_UNIQUE_ID, ATTR_SENSOR_UOM,
                    DATA_LOADED_ENTITIES, DOMAIN)

from .entity import MobileAppEntity, sensor_id

DEPENDENCIES = ['mobile_app']


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mobile app sensor from a config entry."""
    entities = list()

    for config in hass.data[DOMAIN][ENTITY_TYPE].values():
        if config[ATTR_CONFIG_ENTRY_ID] != config_entry.entry_id:
            continue

        entities.append(MobileAppSensor(config))

    async_add_entities(entities)

    @callback
    def handle_sensor_registration(entry_id, data):
        if data[ATTR_CONFIG_ENTRY_ID] != entry_id:
            return

        unique_id = sensor_id(data[CONF_WEBHOOK_ID],
                              data[ATTR_SENSOR_UNIQUE_ID])

        entity_config = hass.data[DOMAIN][ENTITY_TYPE][unique_id]

        if entity_config in hass.data[DOMAIN][DATA_LOADED_ENTITIES]:
            return

        hass.data[DOMAIN][DATA_LOADED_ENTITIES].append(entity_config)

        async_add_entities([MobileAppSensor(data)])

    async_dispatcher_connect(hass,
                             '{}_{}_register'.format(DOMAIN, ENTITY_TYPE),
                             partial(handle_sensor_registration,
                                     config_entry.entry_id))


class MobileAppSensor(MobileAppEntity):
    """Representation of an mobile app sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._config[ATTR_SENSOR_STATE]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._config.get(ATTR_SENSOR_UOM)
