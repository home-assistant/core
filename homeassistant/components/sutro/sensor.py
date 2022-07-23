"""Sensor platform for Sutro."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTRIBUTION,
    DOMAIN,
    ICON_ACIDITY,
    ICON_ALKALINITY,
    ICON_BATTERY,
    ICON_CHLORINE,
    ICON_TEMPERATURE,
    NAME,
    VERSION,
)
from .entity import SutroEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Sutro sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AciditySensor(coordinator, entry),
            AlkalinitySensor(coordinator, entry),
            FreeChlorineSensor(coordinator, entry),
            TemperatureSensor(coordinator, entry),
            BatterySensor(coordinator, entry),
        ]
    )


class SutroSensor(SutroEntity, SensorEntity):
    """sutro Sensor class."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self):
        """Return the parent device information."""
        device_unique_id = self.coordinator.data["me"]["device"]["serialNumber"]
        return {
            "identifiers": {(DOMAIN, device_unique_id)},
            "name": NAME,
            "model": VERSION,
            "manufacturer": NAME,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "attribution": ATTRIBUTION,
            "integration": DOMAIN,
        }


class AciditySensor(SutroSensor):
    """Representation of an Acidity Sensor."""

    _attr_name = f"{NAME} Acidity Sensor"
    _attr_icon = ICON_ACIDITY
    _attr_native_unit_of_measurement = "pH"

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return float(self.coordinator.data["me"]["pool"]["latestReading"]["ph"])

    @property
    def unique_id(self):
        """Return a unique ID to use for the sensor."""
        return f"{self.coordinator.data['me']['device']['serialNumber']}-acidity"


class AlkalinitySensor(SutroSensor):
    """Representation of an Alkalinity Sensor."""

    _attr_name = f"{NAME} Alkalinity Sensor"
    _attr_icon = ICON_ALKALINITY
    _attr_native_unit_of_measurement = "mg/L CaC03"

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return float(self.coordinator.data["me"]["pool"]["latestReading"]["alkalinity"])

    @property
    def unique_id(self):
        """Return a unique ID to use for the sensor."""
        return f"{self.coordinator.data['me']['device']['serialNumber']}-alkalinity"


class FreeChlorineSensor(SutroSensor):
    """Representation of a Free Chlorine Sensor."""

    _attr_name = f"{NAME} Free Chlorine Sensor"
    _attr_icon = ICON_CHLORINE
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return float(self.coordinator.data["me"]["pool"]["latestReading"]["chlorine"])

    @property
    def unique_id(self):
        """Return a unique ID to use for the sensor."""
        return f"{self.coordinator.data['me']['device']['serialNumber']}-chlorine"


class TemperatureSensor(SutroSensor):
    """Representation of a Temperature Sensor."""

    _attr_name = f"{NAME} Temperature Sensor"
    _attr_icon = ICON_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_FAHRENHEIT
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return float(self.coordinator.data["me"]["device"]["temperature"])

    @property
    def unique_id(self):
        """Return a unique ID to use for the sensor."""
        return f"{self.coordinator.data['me']['device']['serialNumber']}-temperature"


class BatterySensor(SutroSensor):
    """Representation of a Battery Sensor."""

    _attr_name = f"{NAME} Battery"
    _attr_icon = ICON_BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return float(self.coordinator.data["me"]["device"]["batteryLevel"])

    @property
    def unique_id(self):
        """Return a unique ID to use for the sensor."""
        return f"{self.coordinator.data['me']['device']['serialNumber']}-battery"
