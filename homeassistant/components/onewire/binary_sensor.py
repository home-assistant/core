"""Support for 1-Wire binary sensors."""
import os

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_TYPE

from .const import CONF_TYPE_OWSERVER, DOMAIN, SENSOR_TYPE_SENSED
from .onewire_entities import OneWireProxyEntity
from .onewirehub import OneWireHub

DEVICE_BINARY_SENSORS = {
    # Family : { path, sensor_type }
    "12": [
        {
            "path": "sensed.A",
            "name": "Sensed A",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
        {
            "path": "sensed.B",
            "name": "Sensed B",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
    ],
    "29": [
        {
            "path": "sensed.0",
            "name": "Sensed 0",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
        {
            "path": "sensed.1",
            "name": "Sensed 1",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
        {
            "path": "sensed.2",
            "name": "Sensed 2",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
        {
            "path": "sensed.3",
            "name": "Sensed 3",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
        {
            "path": "sensed.4",
            "name": "Sensed 4",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
        {
            "path": "sensed.5",
            "name": "Sensed 5",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
        {
            "path": "sensed.6",
            "name": "Sensed 6",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
        {
            "path": "sensed.7",
            "name": "Sensed 7",
            "type": SENSOR_TYPE_SENSED,
            "default_disabled": True,
        },
    ],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up 1-Wire platform."""
    # Only OWServer implementation works with binary sensors
    if config_entry.data[CONF_TYPE] == CONF_TYPE_OWSERVER:
        onewirehub = hass.data[DOMAIN][config_entry.entry_id]

        entities = await hass.async_add_executor_job(get_entities, onewirehub)
        async_add_entities(entities, True)


def get_entities(onewirehub: OneWireHub):
    """Get a list of entities."""
    entities = []

    for device in onewirehub.devices:
        family = device["family"]
        device_type = device["type"]
        device_id = os.path.split(os.path.split(device["path"])[0])[1]

        if family not in DEVICE_BINARY_SENSORS:
            continue
        device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "manufacturer": "Maxim Integrated",
            "model": device_type,
            "name": device_id,
        }
        for entity_specs in DEVICE_BINARY_SENSORS[family]:
            entity_path = os.path.join(
                os.path.split(device["path"])[0], entity_specs["path"]
            )
            entities.append(
                OneWireProxyBinarySensor(
                    device_id=device_id,
                    device_name=device_id,
                    device_info=device_info,
                    entity_path=entity_path,
                    entity_specs=entity_specs,
                    owproxy=onewirehub.owproxy,
                )
            )

    return entities


class OneWireProxyBinarySensor(OneWireProxyEntity, BinarySensorEntity):
    """Implementation of a 1-Wire binary sensor."""

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state
