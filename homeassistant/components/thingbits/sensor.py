"""ThingBits Sensors."""

import thingbits_ha

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from . import ThingbitsEntity
from .const import DOMAIN

SIGNAL_UPDATE_ENTITY = "thingbits_{}"


def send_event(device_id, user_data, data):
    """Send event to HomeAssistant from thingbits_ha (callback)."""

    hass, sensor = user_data
    sensor.value = data
    async_dispatcher_send(hass, SIGNAL_UPDATE_ENTITY.format(device_id))


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the ThingBits binary sensors."""
    thingbits = hass.data[DOMAIN][config.entry_id]
    devices = await hass.async_add_executor_job(thingbits_ha.devices)
    entities = []
    for device in devices:
        if device["type"] in thingbits.SENSOR_TYPES:
            sensor = Sensor(device)
            entities.append(sensor)
            thingbits_ha.listen(device["id"], (hass, sensor), send_event)

    async_add_entities(entities)


class Sensor(ThingbitsEntity, SensorEntity):
    """Representation of a ThingBits sensor."""

    def __init__(self, data):
        """Initialize the sensor."""
        self.data = data
        self._state = None
        self._remove_signal_update = None
        self.value = None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            SIGNAL_UPDATE_ENTITY.format(self.data["id"]),
            self._update_callback,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        self._remove_signal_update()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.data["name"]

    @property
    def state(self):
        """Get the state of the sensor."""
        return self._state

    async def async_update(self):
        """Update sensor state."""
        self._state = self.value

    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.data["id"]

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self.data["type"] == "Light":
            return "%"
        elif self.data["type"] == "Sound":
            return "V"
        elif self.data["type"] == "T,RH":
            return "°F"
        elif self.data["type"] == "Temp":
            return "°F"
        else:
            return None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self.data["type"] == "Light":
            return "mdi:brightness-percent"
        elif self.data["type"] == "Sound":
            return "mdi:volume-source"
        elif self.data["type"] == "T,RH":
            return "mdi:water-percent"
        elif self.data["type"] == "Temp":
            return "mdi:thermometer"
        else:
            return None
