"""Abstraction form AEMET OpenData sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, SENSOR_DEVICE_CLASS, SENSOR_NAME, SENSOR_UNIT
from .weather_update_coordinator import WeatherUpdateCoordinator


class AbstractAemetSensor(CoordinatorEntity, SensorEntity):
    """Abstract class for an AEMET OpenData sensor."""

    def __init__(
        self,
        name,
        unique_id,
        sensor_type,
        sensor_configuration,
        coordinator: WeatherUpdateCoordinator,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._name = name
        self._unique_id = unique_id
        self._sensor_type = sensor_type
        self._sensor_name = sensor_configuration[SENSOR_NAME]
        self._unit_of_measurement = sensor_configuration.get(SENSOR_UNIT)
        self._device_class = sensor_configuration.get(SENSOR_DEVICE_CLASS)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._sensor_name}"

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def device_class(self):
        """Return the device_class."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}
