"""Sensors exposing properties of the softener device."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from aioaquacell import Softener

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import Coordinator
from .entity import AquacellEntity

SCAN_INTERVAL = timedelta(seconds=3600)
PARALLEL_UPDATES = 1


@dataclass
class AquacellEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Softener], str | int | float | None]


@dataclass
class SoftenerEntityDescription(
    SensorEntityDescription, AquacellEntityDescriptionMixin
):
    """Describes Softener sensor entity."""


SENSORS: tuple[SoftenerEntityDescription, ...] = (
    SoftenerEntityDescription(
        key="salt_leftpercentage",
        translation_key="salt_leftpercentage",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:basket-fill",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda softener: cast(int, softener.salt.leftPercent),
    ),
    SoftenerEntityDescription(
        key="salt_rightpercentage",
        translation_key="salt_rightpercentage",
        icon="mdi:basket-fill",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda softener: cast(int, softener.salt.rightPercent),
    ),
    SoftenerEntityDescription(
        key="salt_leftdays",
        translation_key="salt_leftdays",
        icon="mdi:calendar-today",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda softener: softener.salt.leftDays,
    ),
    SoftenerEntityDescription(
        key="salt_rightdays",
        translation_key="salt_rightdays",
        icon="mdi:calendar-today",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda softener: softener.salt.rightDays,
    ),
    SoftenerEntityDescription(
        key="fw_version",
        translation_key="fw_version",
        icon="mdi:chip",
        value_fn=lambda softener: softener.fwVersion,
    ),
    SoftenerEntityDescription(
        key="name",
        translation_key="name",
        value_fn=lambda softener: softener.name,
    ),
    SoftenerEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda softener: softener.battery,
    ),
    SoftenerEntityDescription(
        key="last_update",
        translation_key="last_update",
        icon="mdi:update",
        value_fn=lambda softener: datetime.fromtimestamp(
            cast(float, softener.lastUpdate) / 1000
        ).isoformat(),
    ),
    SoftenerEntityDescription(
        key="wifi_level",
        translation_key="wifi_level",
        icon="mdi:wifi",
        value_fn=lambda softener: softener.wifiLevel,
    ),
    SoftenerEntityDescription(
        key="lid_in_place",
        translation_key="lid_in_place",
        icon="mdi:check",
        native_unit_of_measurement="",
        value_fn=lambda softener: softener.lidInPlace,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator: Coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for sensor in SENSORS:
        entities.append(SoftenerSensor(coordinator, sensor))

    async_add_entities(entities)


class SoftenerSensor(AquacellEntity, SensorEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    softener: Softener

    def __init__(
        self,
        coordinator: Coordinator,
        description: SoftenerEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator.data[0], coordinator)
        self.description = description
        self.softener = self.coordinator.data[0]

        self._attr_translation_key = description.translation_key

        self._attr_unique_id = description.key
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

        self._attr_icon = description.icon

        self._attr_state_class = description.state_class

        self._attr_device_class = description.device_class

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        return self.description.value_fn(self.softener)
