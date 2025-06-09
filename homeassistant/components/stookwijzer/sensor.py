"""Support for Stookwijzer Sensor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from stookwijzer import Stookwijzer

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StookwijzerConfigEntry, StookwijzerCoordinator


@dataclass(kw_only=True, frozen=True)
class StookwijzerSensorDescription(SensorEntityDescription):
    """Class describing Stookwijzer sensor entities."""

    value_fn: Callable[[Stookwijzer], int | float | str | None]


STOOKWIJZER_SENSORS = [
    StookwijzerSensorDescription(
        key="windspeed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.BEAUFORT,
        device_class=SensorDeviceClass.WIND_SPEED,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda client: client.windspeed_ms,
    ),
    StookwijzerSensorDescription(
        key="air_quality_index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda client: client.lki,
    ),
    StookwijzerSensorDescription(
        key="advice",
        translation_key="advice",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda client: client.advice,
        options=["code_yellow", "code_orange", "code_red"],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StookwijzerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Stookwijzer sensor from a config entry."""
    async_add_entities(
        StookwijzerSensor(description, entry) for description in STOOKWIJZER_SENSORS
    )


class StookwijzerSensor(CoordinatorEntity[StookwijzerCoordinator], SensorEntity):
    """Defines a Stookwijzer binary sensor."""

    entity_description: StookwijzerSensorDescription
    _attr_attribution = "Data provided by atlasleefomgeving.nl"
    _attr_has_entity_name = True

    def __init__(
        self,
        description: StookwijzerSensorDescription,
        entry: StookwijzerConfigEntry,
    ) -> None:
        """Initialize a Stookwijzer device."""
        super().__init__(entry.runtime_data)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Atlas Leefomgeving",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.atlasleefomgeving.nl/stookwijzer",
        )

    @property
    def native_value(self) -> int | float | str | None:
        """Return the state of the device."""
        return self.entity_description.value_fn(self.coordinator.client)
