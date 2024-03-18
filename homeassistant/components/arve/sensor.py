"""Support for Arve devices."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArveCoordinator
from .entity import ArveDeviceEntity, ArveDeviceEntityDescription

SENSORS: tuple[ArveDeviceEntityDescription, ...] = (
    ArveDeviceEntityDescription(
        key="CO2",
        translation_key="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        value_fn=lambda arve_data: getattr(arve_data, "co2"),
    ),
    ArveDeviceEntityDescription(
        key="AQI",
        translation_key="aqi",
        native_unit_of_measurement=None,
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda arve_data: getattr(arve_data, "aqi"),
    ),
    ArveDeviceEntityDescription(
        key="Humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        value_fn=lambda arve_data: getattr(arve_data, "humidity"),
    ),
    ArveDeviceEntityDescription(
        key="PM10",
        translation_key="pm10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        value_fn=lambda arve_data: getattr(arve_data, "pm10"),
    ),
    ArveDeviceEntityDescription(
        key="PM25",
        translation_key="pm25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        value_fn=lambda arve_data: getattr(arve_data, "pm25"),
    ),
    ArveDeviceEntityDescription(
        key="Temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda arve_data: getattr(arve_data, "temperature"),
    ),
    ArveDeviceEntityDescription(
        key="TVOC",
        translation_key="tvoc",
        native_unit_of_measurement=None,
        value_fn=lambda arve_data: getattr(arve_data, "tvoc"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Arve device based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [ArveDevice(coordinator, description) for description in SENSORS],
        True,
    )


class ArveDevice(ArveDeviceEntity, SensorEntity):
    """Define an Arve device."""

    entity_description: ArveDeviceEntityDescription

    def __init__(
        self,
        coordinator: ArveCoordinator,
        description: ArveDeviceEntityDescription,
    ) -> None:
        """Initialize Arve device."""
        super().__init__(coordinator, description)
        self.coordinator = coordinator

    @property
    def native_value(self) -> int | float:
        """State of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the Arve device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.sn)},
            manufacturer="Calanda Air AG",
            model="Arve Sens Pro",
            sw_version="1.0.0",
        )
