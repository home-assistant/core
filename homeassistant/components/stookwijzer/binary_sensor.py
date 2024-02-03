"""Support for Stookwijzer Binary Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StookwijzerCoordinator, StookwijzerData
from .entity import StookwijzerEntity


@dataclass(frozen=True)
class StookwijzerSensorDescriptionMixin:
    """Required values for Stookwijzer binary sensors."""

    value_fn: Callable[[StookwijzerCoordinator], bool | None]
    attr_fn: Callable[[StookwijzerCoordinator], list | None]


@dataclass(frozen=True)
class StookwijzerBinarySensorDescription(
    BinarySensorEntityDescription,
    StookwijzerSensorDescriptionMixin,
):
    """Class describing Stookwijzer binary sensor entities."""


STOOKWIJZER_BINARY_SENSORS = (
    StookwijzerBinarySensorDescription(
        key="stookalert",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=lambda StookwijzerCoordinator: cast(
            bool | None, StookwijzerCoordinator.client.alert
        ),
        attr_fn=lambda StookwijzerCoordinator: cast(
            list | None, StookwijzerCoordinator.client.forecast_alert
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stookwijzer binary sensor from a config entry."""
    data: StookwijzerData = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.coordinator

    assert coordinator is not None
    async_add_entities(
        StookwijzerBinarySensor(description, coordinator, entry)
        for description in STOOKWIJZER_BINARY_SENSORS
    )


class StookwijzerBinarySensor(
    StookwijzerEntity, CoordinatorEntity[StookwijzerCoordinator], BinarySensorEntity
):
    """Defines a Stookwijzer binary sensor."""

    entity_description: StookwijzerBinarySensorDescription

    def __init__(
        self,
        description: StookwijzerBinarySensorDescription,
        coordinator: StookwijzerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(description, coordinator, entry)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the device."""
        return self.entity_description.value_fn(self._coordinator)
