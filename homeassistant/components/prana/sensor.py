"""Sensor platform for Prana integration."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, PranaSensorType
from .coordinator import PranaCoordinator

PARALLEL_UPDATES = 1


class PranaSensor(SensorEntity):
    """Representation of a Prana sensor value."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(
        self,
        unique_id: str,
        name: str,
        coordinator: PranaCoordinator,
        sensor_key: str,
        device_info: DeviceInfo,
        sensor_type: str,
    ) -> None:
        """Initialize sensor entity."""
        self._attr_unique_id = unique_id
        self.coordinator = coordinator
        self.sensor_key = sensor_key
        self._attr_device_info = device_info
        self.sensor_type = sensor_type
        if self.sensor_type == PranaSensorType.INSIDE_TEMPERATURE:
            self._attr_translation_key = "inside_temperature"
        elif self.sensor_type == PranaSensorType.INSIDE_TEMPERATURE_2:
            self._attr_translation_key = "inside_temperature_2"
        elif self.sensor_type == PranaSensorType.OUTSIDE_TEMPERATURE:
            self._attr_translation_key = "outside_temperature"
        elif self.sensor_type == PranaSensorType.OUTSIDE_TEMPERATURE_2:
            self._attr_translation_key = "outside_temperature_2"
        elif self.sensor_type == PranaSensorType.HUMIDITY:
            self._attr_translation_key = "humidity"
        elif self.sensor_type == PranaSensorType.VOC:
            self._attr_translation_key = "voc"
        elif self.sensor_type == PranaSensorType.AIR_PRESSURE:
            self._attr_translation_key = "air_pressure"
        elif self.sensor_type == PranaSensorType.CO2:
            self._attr_translation_key = "co2"
        else:
            self._attr_translation_key = "sensor"
        self._attr_icon = self.get_icon()
        if sensor_type in (
            PranaSensorType.INSIDE_TEMPERATURE,
            PranaSensorType.INSIDE_TEMPERATURE_2,
            PranaSensorType.OUTSIDE_TEMPERATURE,
            PranaSensorType.OUTSIDE_TEMPERATURE_2,
        ):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif sensor_type == PranaSensorType.HUMIDITY:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif sensor_type == PranaSensorType.AIR_PRESSURE:
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_native_unit_of_measurement = UnitOfPressure.MMHG
        elif sensor_type == PranaSensorType.CO2:
            self._attr_device_class = SensorDeviceClass.CO2
            self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
        else:
            self._attr_device_class = None

    def get_icon(self) -> str:
        """Return icon for the sensor type."""
        if self.sensor_type in (
            PranaSensorType.INSIDE_TEMPERATURE,
            PranaSensorType.INSIDE_TEMPERATURE_2,
        ):
            return "mdi:home-thermometer"
        if self.sensor_type in (
            PranaSensorType.OUTSIDE_TEMPERATURE,
            PranaSensorType.OUTSIDE_TEMPERATURE_2,
        ):
            return "mdi:thermometer"
        if self.sensor_type == PranaSensorType.HUMIDITY:
            return "mdi:water-percent"
        if self.sensor_type == PranaSensorType.VOC:
            return "mdi:chemical-weapon"
        if self.sensor_type == PranaSensorType.AIR_PRESSURE:
            return "mdi:gauge"
        if self.sensor_type == PranaSensorType.CO2:
            return "mdi:molecule-co2"
        return "mdi:help"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        key = self.sensor_type  # replace self._key
        value = self.coordinator.data.get(key) if self.coordinator.data else None
        if isinstance(value, (str, int, float)):
            return value
        return None

    @property
    def available(self) -> bool:
        """Return availability based on presence of key in data."""
        return self.coordinator.data.get(self.sensor_type) is not None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana sensor entities from a config entry."""
    coordinator: PranaCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get("name", "Prana Device"),
        manufacturer="Prana",
        model="PRANA RECUPERATOR",
    )

    def _maybe(sensor_type: str, key: str, label: str) -> PranaSensor | None:
        if coordinator.data.get(sensor_type) is None:
            return None
        return PranaSensor(
            unique_id=f"{entry.entry_id}-{key}",
            name=label,
            coordinator=coordinator,
            sensor_key=key,
            device_info=device_info,
            sensor_type=sensor_type,
        )

    sensors = [
        _maybe(
            PranaSensorType.INSIDE_TEMPERATURE,
            "inside_temperature",
            "Inside Temperature",
        ),
        _maybe(
            PranaSensorType.OUTSIDE_TEMPERATURE,
            "outside_temperature",
            "Outside Temperature",
        ),
        _maybe(
            PranaSensorType.INSIDE_TEMPERATURE_2,
            "inside_temperature2",
            "Inside Temperature 2",
        ),
        _maybe(
            PranaSensorType.OUTSIDE_TEMPERATURE_2,
            "outside_temperature2",
            "Outside Temperature 2",
        ),
        _maybe(PranaSensorType.HUMIDITY, "humidity", "Humidity"),
        _maybe(PranaSensorType.VOC, "voc", "VOC"),
        _maybe(PranaSensorType.AIR_PRESSURE, "air_pressure", "Air Pressure"),
        _maybe(PranaSensorType.CO2, "co2", "CO2"),
    ]
    async_add_entities([s for s in sensors if s is not None], update_before_add=True)
