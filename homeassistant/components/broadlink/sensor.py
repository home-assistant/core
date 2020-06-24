"""Support for Broadlink sensors."""
from homeassistant.const import TEMP_CELSIUS, UNIT_PERCENTAGE
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

SENSOR_TYPES = {
    "temperature": ["Temperature", TEMP_CELSIUS],
    "air_quality": ["Air Quality", " "],
    "humidity": ["Humidity", UNIT_PERCENTAGE],
    "light": ["Light", " "],
    "noise": ["Noise", " "],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink sensor."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    sensor_data = device.coordinator.data
    sensors = [
        BroadlinkSensor(device, monitored_condition)
        for monitored_condition in sensor_data
        if sensor_data[monitored_condition] or device.api.type == "A1"
    ]
    async_add_entities(sensors)


class BroadlinkSensor(Entity):
    """Representation of a Broadlink sensor."""

    def __init__(self, device, monitored_condition):
        """Initialize the sensor."""
        self._device = device
        self._coordinator = device.coordinator
        self._monitored_condition = monitored_condition
        self._unit_of_measurement = SENSOR_TYPES[monitored_condition][1]

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        return f"{self._device.unique_id}-{self._monitored_condition}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device.name} {SENSOR_TYPES[self._monitored_condition][0]}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._coordinator.data[self._monitored_condition]

    @property
    def available(self):
        """Return True if the sensor is available."""
        return self._coordinator.last_update_success

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return True if the sensor has to be polled for state."""
        return False

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "manufacturer": self._device.api.manufacturer,
            "model": self._device.api.model,
            "name": self._device.name,
            "sw_version": self._device.fw_version,
        }

    async def async_added_to_hass(self):
        """Call when the sensor is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update the sensor."""
        await self._coordinator.async_request_refresh()
