"""Binary sensors for Yardian integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import YardianConfigEntry, YardianUpdateCoordinator
from .entity import YardianEntity, YardianZoneEntity


@dataclass(kw_only=True, frozen=True)
class YardianBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Entity description for Yardian binary sensors."""

    value_fn: Callable[[YardianUpdateCoordinator], bool | None]


def _zone_enabled_value(
    coordinator: YardianUpdateCoordinator, zone_id: int
) -> bool | None:
    """Return True if zone is enabled on controller."""
    try:
        return coordinator.data.zones[zone_id].is_enabled
    except IndexError:
        return None


def _zone_value_factory(
    zone_id: int,
) -> Callable[[YardianUpdateCoordinator], bool | None]:
    """Return a callable evaluating whether a zone is enabled."""

    def value(coordinator: YardianUpdateCoordinator) -> bool | None:
        return _zone_enabled_value(coordinator, zone_id)

    return value


def _standby_value(coordinator: YardianUpdateCoordinator) -> bool:
    """Return True if the device is in standby mode safely."""
    standby_end = coordinator.data.oper_info.get("iStandby")

    # Guard against missing data (None)
    if standby_end is None:
        return False

    return standby_end > dt_util.utcnow().timestamp()


SENSOR_DESCRIPTIONS: tuple[YardianBinarySensorEntityDescription, ...] = (
    YardianBinarySensorEntityDescription(
        key="watering_running",
        translation_key="watering_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda coordinator: bool(coordinator.data.active_zones),
    ),
    YardianBinarySensorEntityDescription(
        key="standby",
        translation_key="standby",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_standby_value,
    ),
    YardianBinarySensorEntityDescription(
        key="freeze_prevent",
        translation_key="freeze_prevent_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda coordinator: bool(
            coordinator.data.oper_info.get("fFreezePrevent", 0)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: YardianConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yardian binary sensors."""
    coordinator = config_entry.runtime_data

    # 1. Global/Main device sensors
    entities: list[BinarySensorEntity] = [
        YardianBinarySensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    # 2. Zone/Child device sensors
    for zone_id in range(len(coordinator.data.zones)):
        description = YardianBinarySensorEntityDescription(
            key=f"zone_enabled_{zone_id}",
            translation_key="zone_enabled",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=_zone_value_factory(zone_id),
        )
        entities.append(YardianZoneBinarySensor(coordinator, description, zone_id))

    async_add_entities(entities)


class YardianBinarySensor(YardianEntity, BinarySensorEntity):
    """Representation of a Yardian binary sensor assigned to the main device."""

    entity_description: YardianBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: YardianUpdateCoordinator,
        description: YardianBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Yardian binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.yid}-{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the current state based on the description's value function."""
        return self.entity_description.value_fn(self.coordinator)


class YardianZoneBinarySensor(YardianZoneEntity, BinarySensorEntity):
    """Representation of a Yardian binary sensor assigned to a zone child device."""

    entity_description: YardianBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: YardianUpdateCoordinator,
        description: YardianBinarySensorEntityDescription,
        zone_id: int,
    ) -> None:
        """Initialize the Yardian zone binary sensor."""
        super().__init__(coordinator, zone_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.yid}-{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the current state based on the description's value function."""
        return self.entity_description.value_fn(self.coordinator)
