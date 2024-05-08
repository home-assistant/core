"""Sensors exposing properties of the softener device."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from aioaquacell import Softener
from sensor import SensorDeviceClass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
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

    value_fn: Callable[[Softener], int | float | str]


@dataclass
class SoftenerEntityDescription(
    SensorEntityDescription, AquacellEntityDescriptionMixin
):
    """Describes Softener sensor entity."""


SENSORS: tuple[SoftenerEntityDescription, ...] = (
    SoftenerEntityDescription(
        key="salt_leftpercentage",
        translation_key="salt_leftpercentage",
        icon="mdi:magnify",
        native_unit_of_measurement="%",
        value_fn=lambda softener: softener.salt.leftPercent,
    ),
    SoftenerEntityDescription(
        key="salt_rightpercentage",
        translation_key="salt_rightpercentage",
        icon="mdi:magnify",
        native_unit_of_measurement="%",
        value_fn=lambda softener: softener.salt.rightPercent,
    ),
    SoftenerEntityDescription(
        key="salt_leftdays",
        translation_key="salt_leftdays",
        icon="mdi:magnify",
        native_unit_of_measurement="days",
        value_fn=lambda softener: softener.salt.leftDays,
    ),
    SoftenerEntityDescription(
        key="salt_rightdays",
        translation_key="salt_rightdays",
        icon="mdi:magnify",
        native_unit_of_measurement="days",
        value_fn=lambda softener: softener.salt.rightDays,
    ),
    SoftenerEntityDescription(
        key="fw_version",
        translation_key="fw_version",
        icon="mdi:magnify",
        native_unit_of_measurement="",
        value_fn=lambda softener: softener.fwVersion,
    ),
    SoftenerEntityDescription(
        key="name",
        translation_key="name",
        icon="mdi:magnify",
        native_unit_of_measurement="",
        value_fn=lambda softener: softener.name,
    ),
    SoftenerEntityDescription(
        key="battery",
        translation_key="battery",
        icon="mdi:battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement="%",
        value_fn=lambda softener: softener.battery,
    ),
    SoftenerEntityDescription(
        key="last_update",
        translation_key="last_update",
        icon="mdi:update",
        native_unit_of_measurement="",
        value_fn=lambda softener: softener.lastUpdate,
    ),
    SoftenerEntityDescription(
        key="wifi_level",
        translation_key="wifi_level",
        icon="mdi:wifi",
        native_unit_of_measurement="",
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
        self._attr_native_unit_of_measurement = description.unit_of_measurement

        self._attr_icon = description.icon

    @property
    def native_value(self) -> int | float | str:
        """Return the state of the sensor."""
        return self.description.value_fn(self.softener)
