"""Sensor platform for the Cookidoo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import SUBSCRIPTION_MAP
from .coordinator import (
    CookidooConfigEntry,
    CookidooData,
    CookidooDataUpdateCoordinator,
)
from .entity import CookidooBaseEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class CookidooSensorEntityDescription(SensorEntityDescription):
    """Cookidoo Sensor Description."""

    value_fn: Callable[[CookidooData], StateType | datetime]


class CookidooSensor(StrEnum):
    """Cookidoo sensors."""

    SUBSCRIPTION = "subscription"
    EXPIRES = "expires"


SENSOR_DESCRIPTIONS: tuple[CookidooSensorEntityDescription, ...] = (
    CookidooSensorEntityDescription(
        key=CookidooSensor.SUBSCRIPTION,
        translation_key=CookidooSensor.SUBSCRIPTION,
        value_fn=(
            lambda data: SUBSCRIPTION_MAP[data.subscription.type]
            if data.subscription
            else SUBSCRIPTION_MAP["NONE"]
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        options=list(SUBSCRIPTION_MAP.values()),
        device_class=SensorDeviceClass.ENUM,
    ),
    CookidooSensorEntityDescription(
        key=CookidooSensor.EXPIRES,
        translation_key=CookidooSensor.EXPIRES,
        value_fn=(
            lambda data: dt_util.parse_datetime(data.subscription.expires)
            if data.subscription
            else None
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CookidooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        CookidooSensorEntity(
            coordinator,
            description,
        )
        for description in SENSOR_DESCRIPTIONS
    )


class CookidooSensorEntity(CookidooBaseEntity, SensorEntity):
    """A sensor entity."""

    entity_description: CookidooSensorEntityDescription

    def __init__(
        self,
        coordinator: CookidooDataUpdateCoordinator,
        entity_description: CookidooSensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{self.entity_description.key}"
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)
