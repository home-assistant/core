"""Support for Stookwijzer Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, AdviceState
from .coordinator import StookwijzerCoordinator


@dataclass(kw_only=True, frozen=True)
class StookwijzerSensorDescription(SensorEntityDescription):
    """Class describing Stookwijzer sensor entities."""

    value_fn: Callable[[StookwijzerCoordinator], int | float | str | None]


STOOKWIJZER_SENSORS = [
    StookwijzerSensorDescription(
        key="windspeed",
        translation_key="windspeed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.BEAUFORT,
        device_class=SensorDeviceClass.WIND_SPEED,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda StookwijzerCoordinator: StookwijzerCoordinator.client.windspeed_ms,
    ),
    StookwijzerSensorDescription(
        key="air_quality_index",
        translation_key="air_quality_index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda StookwijzerCoordinator: StookwijzerCoordinator.client.lki,
    ),
    StookwijzerSensorDescription(
        key="advice",
        translation_key="advice",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda StookwijzerCoordinator: AdviceState(
            StookwijzerCoordinator.client.advice
        ).value,
        options=[cls.value for cls in AdviceState],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stookwijzer sensor from a config entry."""

    async_add_entities(
        StookwijzerSensor(description, entry) for description in STOOKWIJZER_SENSORS
    )


class StookwijzerSensor(CoordinatorEntity, SensorEntity):
    """Defines a Stookwijzer sensor."""

    entity_description: StookwijzerSensorDescription
    _attr_attribution = "Data provided by atlasleefomgeving.nl"
    _attr_has_entity_name = True

    def __init__(
        self,
        description: StookwijzerSensorDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Sensor Entity."""
        self.entity_description = description
        self._coordinator = entry.runtime_data

        super().__init__(self._coordinator)

        self._attr_unique_id = f"{entry.entry_id}{DOMAIN}{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Atlas Leefomgeving",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.atlasleefomgeving.nl/stookwijzer",
        )

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        value = self.entity_description.value_fn(self._coordinator)
        return str(value) if value is not None else value
