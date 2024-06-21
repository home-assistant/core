import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
import os
import json

_LOGGER = logging.getLogger(__name__)

ICONS_PATH = os.path.join(os.path.dirname(__file__), 'icons.json')
with open(ICONS_PATH, 'r') as f:
    ICONS = json.load(f)


async def async_setup_entry(hass, config_entry, async_add_sensor_entities):
    """Set up the IoTMeter sensors from a config entry."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    coordinator.async_add_sensor_entities = async_add_sensor_entities  # Store the function in the coordinator
    hass.data[DOMAIN]["platform"] = async_add_sensor_entities
    _LOGGER.debug("async_add_sensor_entities set in coordinator")

    await coordinator.async_request_refresh()


class TranslatableSensorEntity(CoordinatorEntity, SensorEntity):
    """A sensor entity that can be localized."""

    def __init__(self, coordinator, sensor_type, translations, unit_of_measurement):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type.replace(' ', '_').lower()
        self._translations = translations
        self._attr_name = self.get_localized_name()
        self._attr_unique_id = f"iotmeter_{self._sensor_type}"
        self._attr_device_class = "measurement"
        self._attr_state_class = "measurement"
        self._attr_native_unit_of_measurement = unit_of_measurement

    def get_localized_name(self):
        """Return the localized name for the sensor."""
        key = f"component.iotmeter.entity.sensor.{self._sensor_type}"
        localized_name = self._translations.get(key)
        return localized_name or self._sensor_type


class TotalPowerSensor(TranslatableSensorEntity):
    """Representation of the total current sensor."""

    def __init__(self, coordinator, sensor_type, translations, unit_of_measurement):
        super().__init__(coordinator, sensor_type, translations, unit_of_measurement)

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
            "P1": round(self.coordinator.data.get('P1') / 1000, 2),
            "P2": round(self.coordinator.data.get('P2') / 1000, 2),
            "P3": round(self.coordinator.data.get('P3') / 1000, 2),
        }

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(f"sensor.{self._attr_unique_id}")


class ConsumptionEnergySensor(TranslatableSensorEntity):

    def __init__(self, coordinator, sensor_type, translations, unit_of_measurement):
        super().__init__(coordinator, sensor_type, translations, unit_of_measurement)

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
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(f"sensor.{self._attr_unique_id}")


class GenerationEnergySensor(TranslatableSensorEntity):

    def __init__(self, coordinator, sensor_type, translations, unit_of_measurement):
        super().__init__(coordinator, sensor_type, translations, unit_of_measurement)

    @property
    def state(self):
        e1 = self.coordinator.data.get("E1tN")
        e2 = self.coordinator.data.get("E2tN")
        e3 = self.coordinator.data.get("E3tN")
        if e1 is not None and e2 is not None and e3 is not None:
            total_energy = (float(e1) + float(e2) + float(e3)) / 1000
            return round(total_energy)
        return None

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(f"sensor.{self._attr_unique_id}")

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if func := self.entity_description.value:
            return func(self._sensor_data.getValue())

        return self._sensor_data.getValue()


class EvseSensor(TranslatableSensorEntity):

    def __init__(self, coordinator, sensor_type, translations, unit_of_measurement, smartmodule: bool = False):
        super().__init__(coordinator, sensor_type, translations, unit_of_measurement)
        self._is_smartmodule: bool = smartmodule

    @property
    def state(self):
        evse_state = self.coordinator.data.get("EV_STATE")
        if evse_state is not None:
            if not self._is_smartmodule:
                evse_state = evse_state[0]
            if 0 <= evse_state <= 3:
                key = f"component.iotmeter.entity.sensor.evse_status.{evse_state}"
                status = self._translations.get(key)
                return status
            else:
                'N/A'
        return None

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICONS.get(f"sensor.{self._attr_unique_id}")


