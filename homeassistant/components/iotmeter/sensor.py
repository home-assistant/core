"""Module for IoTMeter sensor entities in Home Assistant."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_sensor_entities: AddEntitiesCallback,
) -> None:
    """Set up the IoTMeter sensors from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    coordinator.async_add_sensor_entities = (
        async_add_sensor_entities  # Store the function in the coordinator
    )
    hass.data[DOMAIN]["platform"] = async_add_sensor_entities
    _LOGGER.debug("async_add_sensor_entities set in coordinator")
    await coordinator.async_request_refresh()


class TranslatableSensorEntity(CoordinatorEntity, SensorEntity):
    """A sensor entity that can be localized."""

    def __init__(
        self, coordinator, sensor_type, translations, unit_of_measurement
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type.replace(" ", "_").lower()
        self._translations = translations
        self._attr_name = self.get_localized_name()
        self._attr_native_unit_of_measurement = unit_of_measurement

    def get_localized_name(self):
        """Return the localized name for the sensor."""
        key = f"component.iotmeter.entity.sensor.{self._sensor_type}"
        localized_name = self._translations.get(key)
        return localized_name or self._sensor_type


class TotalPowerSensor(TranslatableSensorEntity):
    """Representation of the total power sensor."""

    def __init__(self, coordinator, sensor_type, translations, unit_of_measurement):
        """Initialize the total power sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type.replace(" ", "_").lower()
        self._translations = translations
        self._attr_native_unit_of_measurement = unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        p1 = self.coordinator.data.get("P1")
        p2 = self.coordinator.data.get("P2")
        p3 = self.coordinator.data.get("P3")
        if p1 is not None and p2 is not None and p3 is not None:
            total_power = (float(p1) + float(p2) + float(p3)) / 1000
            return round(total_power, 2)
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "P1": round(self.coordinator.data.get("P1") / 1000, 2),
            "P2": round(self.coordinator.data.get("P2") / 1000, 2),
            "P3": round(self.coordinator.data.get("P3") / 1000, 2),
        }

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:home-lightning-bolt"


class ConsumptionEnergySensor(TranslatableSensorEntity):
    """Representation of the consumption energy sensor."""

    def __init__(self, coordinator, sensor_type, translations, unit_of_measurement):
        """Initialize the consumption energy sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type.replace(" ", "_").lower()
        self._translations = translations
        self._attr_native_unit_of_measurement = unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        e1 = self.coordinator.data.get("E1tP")
        e2 = self.coordinator.data.get("E2tP")
        e3 = self.coordinator.data.get("E3tP")
        if e1 is not None and e2 is not None and e3 is not None:
            total_energy = (float(e1) + float(e2) + float(e3)) / 1000
            return round(total_energy)
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:transmission-tower"


class GenerationEnergySensor(TranslatableSensorEntity):
    """Representation of the generation energy sensor."""

    def __init__(self, coordinator, sensor_type, translations, unit_of_measurement):
        """Initialize the generation energy sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type.replace(" ", "_").lower()
        self._translations = translations
        self._attr_native_unit_of_measurement = unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        e1 = self.coordinator.data.get("E1tN")
        e2 = self.coordinator.data.get("E2tN")
        e3 = self.coordinator.data.get("E3tN")
        if e1 is not None and e2 is not None and e3 is not None:
            total_energy = (float(e1) + float(e2) + float(e3)) / 1000
            return round(total_energy)
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:solar-power-variant"


class EvseSensor(TranslatableSensorEntity):
    """Representation of the EVSE sensor."""

    def __init__(
        self,
        coordinator,
        sensor_type,
        translations,
        unit_of_measurement,
        smartmodule: bool = False,
    ) -> None:
        """Initialize the EVSE sensor."""
        super().__init__(coordinator, sensor_type, translations, unit_of_measurement)

    @property
    def state(self):
        """Return the state of the sensor."""
        evse_state = self.coordinator.data.get("EV_STATE")
        if evse_state is not None:
            if not self._is_smartmodule:
                evse_state = evse_state[0]
            if 0 <= evse_state <= 3:
                key = f"component.iotmeter.entity.sensor.evse_status.{evse_state}"
                return self._translations.get(key)
            return "N/A"
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:ev-station"
