"""Sensors for Yardian integration."""

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
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import YardianUpdateCoordinator

# Values above this threshold indicate the API returned an absolute
# timestamp instead of a relative delay, so convert to a remaining delta.
_OPER_INFO_ABSOLUTE_THRESHOLD = 365 * 24 * 3600


@dataclass(kw_only=True, frozen=True)
class YardianSensorEntityDescription(SensorEntityDescription):
    """Entity description for Yardian sensors."""

    value_fn: Callable[[YardianUpdateCoordinator], StateType]


def _zone_delay_value(coordinator: YardianUpdateCoordinator) -> StateType:
    """Return zone delay duration in seconds."""
    val = coordinator.data.oper_info.get("iSensorDelay")
    if not isinstance(val, int):
        return None

    delay = val

    if delay > _OPER_INFO_ABSOLUTE_THRESHOLD:
        now = int(dt_util.utcnow().timestamp())
        return max(0, delay - now)

    return max(0, delay)


SENSOR_DESCRIPTIONS: tuple[YardianSensorEntityDescription, ...] = (
    YardianSensorEntityDescription(
        key="rain_delay",
        translation_key="rain_delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.data.oper_info.get("iRainDelay"),
    ),
    YardianSensorEntityDescription(
        key="active_zone_count",
        translation_key="active_zone_count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: len(coordinator.data.active_zones),
    ),
    YardianSensorEntityDescription(
        key="zone_delay",
        translation_key="zone_delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_zone_delay_value,
    ),
    YardianSensorEntityDescription(
        key="water_hammer_duration",
        translation_key="water_hammer_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda coordinator: coordinator.data.oper_info.get(
            "iWaterHammerDuration"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yardian sensors."""
    coordinator: YardianUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        YardianSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
    )


class YardianSensor(CoordinatorEntity[YardianUpdateCoordinator], SensorEntity):
    """Representation of a Yardian sensor defined by description."""

    entity_description: YardianSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YardianUpdateCoordinator,
        description: YardianSensorEntityDescription,
    ) -> None:
        """Initialize the Yardian sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.yid}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> StateType:
        """Return the value provided by the description."""
        return self.entity_description.value_fn(self.coordinator)
