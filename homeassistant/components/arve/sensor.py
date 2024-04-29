"""Sensor platform for Arve devices."""

from collections.abc import Callable
from dataclasses import dataclass

from asyncarve import ArveSensProData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ArveCoordinator
from .entity import ArveDeviceEntity


@dataclass(frozen=True, kw_only=True)
class ArveDeviceEntityDescription(SensorEntityDescription):
    """Describes Arve device entity."""

    value_fn: Callable[[ArveSensProData], float | int]


SENSORS: tuple[ArveDeviceEntityDescription, ...] = (
    ArveDeviceEntityDescription(
        key="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        value_fn=lambda arve_data: arve_data.co2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ArveDeviceEntityDescription(
        key="AQI",
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda arve_data: arve_data.aqi,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ArveDeviceEntityDescription(
        key="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        value_fn=lambda arve_data: arve_data.humidity,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ArveDeviceEntityDescription(
        key="PM10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        value_fn=lambda arve_data: arve_data.pm10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ArveDeviceEntityDescription(
        key="PM25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        value_fn=lambda arve_data: arve_data.pm25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ArveDeviceEntityDescription(
        key="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda arve_data: arve_data.temperature,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ArveDeviceEntityDescription(
        key="TVOC",
        translation_key="tvoc",
        value_fn=lambda arve_data: arve_data.tvoc,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Arve device based on a config entry."""
    coordinator: ArveCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        ArveDevice(coordinator, description, sn)
        for description in SENSORS
        for sn in coordinator.devices.sn
    )


class ArveDevice(ArveDeviceEntity, SensorEntity):
    """Define an Arve device."""

    entity_description: ArveDeviceEntityDescription

    @property
    def native_value(self) -> int | float:
        """State of the sensor."""
        return self.entity_description.value_fn(self.device.sensors)
