"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, POWER_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DATA_COORDINATOR, DOMAIN, SENSOR_TYPE_RATE, SENSORS_INFO


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]
    user_id = config_entry.data[CONF_ID]

    async_add_entities(
        HuisbaasjeSensor(coordinator, user_id=user_id, **sensor_info)
        for sensor_info in SENSORS_INFO
    )


class HuisbaasjeSensor(CoordinatorEntity, SensorEntity):
    """Defines a Huisbaasje sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        user_id: str,
        name: str,
        source_type: str,
        device_class: str = None,
        sensor_type: str = SENSOR_TYPE_RATE,
        unit_of_measurement: str = POWER_WATT,
        icon: str = "mdi:lightning-bolt",
        precision: int = 0,
        state_class: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._user_id = user_id
        self._name = name
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        self._source_type = source_type
        self._sensor_type = sensor_type
        self._icon = icon
        self._precision = precision
        self._attr_state_class = state_class

    @property
    def unique_id(self) -> str:
        """Return an unique id for the sensor."""
        return f"{DOMAIN}_{self._user_id}_{self._source_type}_{self._sensor_type}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def icon(self) -> str:
        """Return the icon to use for the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.coordinator.data[self._source_type][self._sensor_type] is not None:
            return round(
                self.coordinator.data[self._source_type][self._sensor_type],
                self._precision,
            )
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data
            and self._source_type in self.coordinator.data
            and self.coordinator.data[self._source_type]
        )
