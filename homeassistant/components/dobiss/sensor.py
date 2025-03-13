"""Support for dobiss switches."""
import logging

from dobissapi import DobissLightSensor, DobissSensor, DobissTempSensor
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import Entity
from .const import CONF_IGNORE_ZIGBEE_DEVICES, DOMAIN, KEY_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up dobisssensor."""

    _LOGGER.debug(f"Setting up sensor component of {DOMAIN}")
    dobiss = hass.data[DOMAIN][config_entry.entry_id][KEY_API].api

    entities = []
    d_entities = dobiss.get_devices_by_type(DobissTempSensor)
    for d in d_entities:
        if (
            config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES) is not None
            and config_entry.options.get(CONF_IGNORE_ZIGBEE_DEVICES)
            and (d.address in (210, 211))
        ):
            continue
        entities.append(HADobissTempSensor(d))
    d_entities = dobiss.get_devices_by_type(DobissLightSensor)
    for d in d_entities:
        entities.append(HADobissLightSensor(d))
    if entities:
        async_add_entities(entities)


class HADobissSensor(Entity):
    """Dobiss sensor device."""

    should_poll = False

    def __init__(self, dobisssensor: DobissSensor):
        """Init dobiss Sensor device."""
        super().__init__()
        self._dobisssensor = dobisssensor

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, f"address_{self._dobisssensor.address}")},
            "name": f"Dobiss Device {self._dobisssensor.address}",
            "manufacturer": "dobiss",
        }

    @property
    def extra_state_attributes(self):
        """Return supported attributes."""
        return self._dobisssensor.attributes

    @property
    def available(self) -> bool:
        """Return True."""
        return True

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._dobisssensor.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._dobisssensor.remove_callback(self.async_write_ha_state)

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self._dobisssensor.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._dobisssensor.object_id


class HADobissLightSensor(HADobissSensor):
    """Dobiss Light Sensor."""

    device_class = SensorDeviceClass.ILLUMINANCE

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "lm"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._dobisssensor.value


class HADobissTempSensor(HADobissSensor):
    """Dobiss Light Sensor."""

    device_class = SensorDeviceClass.TEMPERATURE

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._dobisssensor.value
