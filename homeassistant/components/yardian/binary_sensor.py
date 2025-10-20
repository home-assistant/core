"""Binary sensors for Yardian integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YardianUpdateCoordinator


@dataclass(kw_only=True, frozen=True)
class YardianBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Entity description for Yardian binary sensors."""

    value_fn: Callable[[YardianUpdateCoordinator], bool | None]
    translation_placeholders: dict[str, str] | None = None


def _zone_enabled_value(
    coordinator: YardianUpdateCoordinator, zone_id: int
) -> bool | None:
    """Return True if zone is enabled on controller."""
    try:
        return coordinator.data.zones[zone_id][1] == 1
    except (IndexError, TypeError):
        return None


def _standby_value(coordinator: YardianUpdateCoordinator) -> bool:
    """Return True if controller is in standby mode."""
    return bool(coordinator.data.oper_info.get("iStandby", 0))


def _freeze_prevent_value(coordinator: YardianUpdateCoordinator) -> bool:
    """Return True if freeze prevent is active."""
    return bool(coordinator.data.oper_info.get("fFreezePrevent", 0))


def _zone_value_factory(
    zone_id: int,
) -> Callable[[YardianUpdateCoordinator], bool | None]:
    """Return a callable evaluating whether a zone is enabled."""

    def value(coordinator: YardianUpdateCoordinator) -> bool | None:
        return _zone_enabled_value(coordinator, zone_id)

    return value


SENSOR_DESCRIPTIONS: tuple[YardianBinarySensorEntityDescription, ...] = (
    YardianBinarySensorEntityDescription(
        key="watering_running",
        translation_key="watering_running",
        unique_id_suffix="watering-running",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda coordinator: bool(coordinator.data.active_zones),
    ),
    YardianBinarySensorEntityDescription(
        key="standby",
        translation_key="standby",
        unique_id_suffix="standby",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_standby_value,
    ),
    YardianBinarySensorEntityDescription(
        key="freeze_prevent",
        translation_key="freeze_prevent",
        unique_id_suffix="freeze-prevent",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_freeze_prevent_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Yardian binary sensors."""
    coordinator: YardianUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BinarySensorEntity] = [
        YardianBinarySensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    zone_descriptions = [
        YardianBinarySensorEntityDescription(
            key=f"zone_enabled_{zone_id}",
            translation_key="zone_enabled",
            unique_id_suffix=f"zone-enabled-{zone_id}",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=_zone_value_factory(zone_id),
            translation_placeholders={"zone": str(zone_id + 1)},
        )
        for zone_id in range(len(coordinator.data.zones))
    ]

    entities.extend(
        YardianBinarySensor(coordinator, description)
        for description in zone_descriptions
    )

    async_add_entities(entities)


class YardianBinarySensor(
    CoordinatorEntity[YardianUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Yardian binary sensor based on a description."""

    entity_description: YardianBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YardianUpdateCoordinator,
        description: YardianBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Yardian binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.yid}-{description.key}"
        self._attr_device_info = coordinator.device_info
        if description.translation_placeholders is not None:
            self._attr_translation_placeholders = description.translation_placeholders

    @property
    def is_on(self) -> bool | None:
        """Return the current state based on the description's value function."""
        return self.entity_description.value_fn(self.coordinator)
