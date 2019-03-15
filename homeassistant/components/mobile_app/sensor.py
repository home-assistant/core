"""Sensor platform for mobile_app."""
from functools import partial

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (ATTR_SENSOR_STATE,
                    ATTR_SENSOR_TYPE_SENSOR as ENTITY_TYPE,
                    ATTR_SENSOR_UOM, DATA_DEVICES, DOMAIN)

from .entity import MobileAppEntity

DEPENDENCIES = ['mobile_app']


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mobile app sensor from a config entry."""
    entities = list()

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    for config in hass.data[DOMAIN][ENTITY_TYPE].values():
        if config[CONF_WEBHOOK_ID] != webhook_id:
            continue

        device = hass.data[DOMAIN][DATA_DEVICES][webhook_id]

        entities.append(MobileAppSensor(config, device, config_entry))

    async_add_entities(entities)

    @callback
    def handle_sensor_registration(webhook_id, data):
        if data[CONF_WEBHOOK_ID] != webhook_id:
            return

        device = hass.data[DOMAIN][DATA_DEVICES][data[CONF_WEBHOOK_ID]]

        async_add_entities([MobileAppSensor(data, device, config_entry)])

    async_dispatcher_connect(hass,
                             '{}_{}_register'.format(DOMAIN, ENTITY_TYPE),
                             partial(handle_sensor_registration, webhook_id))


class MobileAppSensor(MobileAppEntity):
    """Representation of an mobile app sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._config[ATTR_SENSOR_STATE]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._config[ATTR_SENSOR_UOM]
