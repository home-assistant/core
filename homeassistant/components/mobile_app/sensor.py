"""Sensor platform for mobile_app."""
from functools import partial

from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID, CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    ATTR_DEVICE_NAME,
    ATTR_SENSOR_ATTRIBUTES,
    ATTR_SENSOR_DEVICE_CLASS,
    ATTR_SENSOR_ICON,
    ATTR_SENSOR_NAME,
    ATTR_SENSOR_STATE,
    ATTR_SENSOR_TYPE,
    ATTR_SENSOR_TYPE_SENSOR as ENTITY_TYPE,
    ATTR_SENSOR_UNIQUE_ID,
    ATTR_SENSOR_UOM,
    DATA_DEVICES,
    DOMAIN,
)
from .entity import MobileAppEntity, unique_id


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up mobile app sensor from a config entry."""
    entities = []

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    entity_registry = await er.async_get_registry(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    for entry in entries:
        if entry.domain != ENTITY_TYPE or entry.disabled_by:
            continue
        config = {
            ATTR_SENSOR_ATTRIBUTES: {},
            ATTR_SENSOR_DEVICE_CLASS: entry.device_class,
            ATTR_SENSOR_ICON: entry.original_icon,
            ATTR_SENSOR_NAME: entry.original_name,
            ATTR_SENSOR_STATE: None,
            ATTR_SENSOR_TYPE: entry.domain,
            ATTR_SENSOR_UNIQUE_ID: entry.unique_id,
            ATTR_SENSOR_UOM: entry.unit_of_measurement,
        }
        entities.append(MobileAppSensor(config, entry.device_id, config_entry))

    async_add_entities(entities)

    @callback
    def handle_sensor_registration(webhook_id, data):
        if data[CONF_WEBHOOK_ID] != webhook_id:
            return

        data[CONF_UNIQUE_ID] = unique_id(
            data[CONF_WEBHOOK_ID], data[ATTR_SENSOR_UNIQUE_ID]
        )
        data[
            CONF_NAME
        ] = f"{config_entry.data[ATTR_DEVICE_NAME]} {data[ATTR_SENSOR_NAME]}"

        device = hass.data[DOMAIN][DATA_DEVICES][data[CONF_WEBHOOK_ID]]

        async_add_entities([MobileAppSensor(data, device, config_entry)])

    async_dispatcher_connect(
        hass,
        f"{DOMAIN}_{ENTITY_TYPE}_register",
        partial(handle_sensor_registration, webhook_id),
    )


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
