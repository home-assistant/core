"""Sensor platform for Arve devices."""

from collections.abc import Callable
from dataclasses import dataclass

from asyncarve import ArveSensProData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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

    value_fn: Callable[[ArveSensProData, str], float | int] = (
        lambda arve_data, key: getattr(arve_data, key.lower())
    )


SENSORS: tuple[ArveDeviceEntityDescription, ...] = (
    ArveDeviceEntityDescription(
        key="CO2",
        translation_key="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
    ),
    ArveDeviceEntityDescription(
        key="AQI",
        translation_key="aqi",
        native_unit_of_measurement=None,
        device_class=SensorDeviceClass.AQI,
    ),
    ArveDeviceEntityDescription(
        key="Humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    ArveDeviceEntityDescription(
        key="PM10",
        translation_key="pm10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
    ),
    ArveDeviceEntityDescription(
        key="PM25",
        translation_key="pm25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
    ),
    ArveDeviceEntityDescription(
        key="Temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    ArveDeviceEntityDescription(
        key="TVOC",
        translation_key="tvoc",
        native_unit_of_measurement=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Arve device based on a config entry."""
    coordinator: ArveCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(ArveDevice(coordinator, description) for description in SENSORS)


class ArveDevice(ArveDeviceEntity, SensorEntity):
    """Define an Arve device."""

    entity_description: ArveDeviceEntityDescription

    @property
    def native_value(self) -> int | float:
        """State of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data, self.entity_description.key
        )
