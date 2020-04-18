"""Binary sensor platform for mobile_app."""
from functools import partial

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_SENSOR_STATE,
    ATTR_SENSOR_TYPE_BINARY_SENSOR as ENTITY_TYPE,
    ATTR_SENSOR_UNIQUE_ID,
    DATA_DEVICES,
    DOMAIN,
)
from .entity import MobileAppEntity, sensor_id


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mobile app binary sensor from a config entry."""
    entities = []

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    for config in hass.data[DOMAIN][ENTITY_TYPE].values():
        if config[CONF_WEBHOOK_ID] != webhook_id:
            continue

        device = hass.data[DOMAIN][DATA_DEVICES][webhook_id]

        entities.append(MobileAppBinarySensor(config, device, config_entry))

    async_add_entities(entities)

    @callback
    def handle_sensor_registration(webhook_id, data):
        if data[CONF_WEBHOOK_ID] != webhook_id:
            return

        unique_id = sensor_id(data[CONF_WEBHOOK_ID], data[ATTR_SENSOR_UNIQUE_ID])

        entity = hass.data[DOMAIN][ENTITY_TYPE][unique_id]

        if "added" in entity:
            return

        entity["added"] = True

        device = hass.data[DOMAIN][DATA_DEVICES][data[CONF_WEBHOOK_ID]]

        async_add_entities([MobileAppBinarySensor(data, device, config_entry)])

    async_dispatcher_connect(
        hass,
        f"{DOMAIN}_{ENTITY_TYPE}_register",
        partial(handle_sensor_registration, webhook_id),
    )


class MobileAppBinarySensor(MobileAppEntity, BinarySensorDevice):
    """Representation of an mobile app binary sensor."""

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._config[ATTR_SENSOR_STATE]
