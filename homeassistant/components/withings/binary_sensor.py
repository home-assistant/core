"""Sensors flow for Withings."""
from __future__ import annotations

from dataclasses import dataclass

from withings_api.common import NotifyAppli

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, Measurement
from .coordinator import WithingsDataUpdateCoordinator
from .entity import WithingsEntity, WithingsEntityDescription


@dataclass
class WithingsBinarySensorEntityDescription(
    BinarySensorEntityDescription, WithingsEntityDescription
):
    """Immutable class for describing withings binary sensor data."""


BINARY_SENSORS = [
    # Webhook measurements.
    WithingsBinarySensorEntityDescription(
        key=Measurement.IN_BED.value,
        measurement=Measurement.IN_BED,
        measure_type=NotifyAppli.BED_IN,
        translation_key="in_bed",
        icon="mdi:bed",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    coordinator: WithingsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        WithingsBinarySensor(coordinator, attribute) for attribute in BINARY_SENSORS
    ]

    async_add_entities(entities)


class WithingsBinarySensor(WithingsEntity, BinarySensorEntity):
    """Implementation of a Withings sensor."""

    entity_description: WithingsBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.in_bed
