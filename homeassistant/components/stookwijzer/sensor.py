"""Support for Stookwijzer Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, StookwijzerState
from .coordinator import StookwijzerCoordinator, StookwijzerData
from .entity import StookwijzerEntity


@dataclass(frozen=True)
class StookwijzerSensorDescriptionMixin:
    """Required values for Stookwijzer sensors."""

    value_fn: Callable[[StookwijzerCoordinator], int | float | str | None]
    attr_fn: Callable[[StookwijzerCoordinator], list | None] | None


@dataclass(frozen=True)
class StookwijzerSensorDescription(
    SensorEntityDescription,
    StookwijzerSensorDescriptionMixin,
):
    """Class describing Stookwijzer sensor entities."""


STOOKWIJZER_SENSORS = (
    StookwijzerSensorDescription(
        key="windspeed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda StookwijzerCoordinator: cast(
            float | None, StookwijzerCoordinator.client.windspeed_ms
        ),
        attr_fn=None,
    ),
    StookwijzerSensorDescription(
        key="air quality index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda StookwijzerCoordinator: cast(
            int | None, StookwijzerCoordinator.client.lki
        ),
        attr_fn=None,
    ),
    StookwijzerSensorDescription(
        key="stookwijzer",
        translation_key="stookwijzer",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda StookwijzerCoordinator: cast(
            str | None, StookwijzerState(StookwijzerCoordinator.client.advice).value
        ),
        attr_fn=lambda StookwijzerCoordinator: cast(
            list | None, StookwijzerCoordinator.client.forecast_advice
        ),
        options=[cls.value for cls in StookwijzerState],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stookwijzer sensor from a config entry."""
    data: StookwijzerData = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.coordinator

    assert coordinator is not None
    async_add_entities(
        StookwijzerSensor(description, coordinator, entry)
        for description in STOOKWIJZER_SENSORS
    )


class StookwijzerSensor(
    StookwijzerEntity, CoordinatorEntity[StookwijzerCoordinator], SensorEntity
):
    """Defines a Stookwijzer sensor."""

    entity_description: StookwijzerSensorDescription

    def __init__(
        self,
        description: StookwijzerSensorDescription,
        coordinator: StookwijzerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(description, coordinator, entry)

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        value = self.entity_description.value_fn(self._coordinator)
        return str(value) if value is not None else value
