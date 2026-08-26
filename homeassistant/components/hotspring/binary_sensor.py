"""Support for Hot Spring binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from hotspring import Spa, SpaFailureState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HotSpringConfigEntry, HotSpringDataUpdateCoordinator
from .entity import HotSpringEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HotSpringBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Hot Spring binary sensor entity."""

    is_on_fn: Callable[[Spa], bool | None]


def _is_problem(spa: Spa) -> bool | None:
    """Return False if OK, None if unavailable or unknown."""
    if spa.diagnostics.spa_failure_state is SpaFailureState.OK:
        return False
    return None


BINARY_SENSORS: tuple[HotSpringBinarySensorEntityDescription, ...] = (
    HotSpringBinarySensorEntityDescription(
        key="heating",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda spa: spa.heater.is_on,
    ),
    HotSpringBinarySensorEntityDescription(
        key="spa_connected",
        translation_key="spa_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda spa: spa.connection_status.spa_connected,
    ),
    HotSpringBinarySensorEntityDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=_is_problem,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HotSpringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hot Spring binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        HotSpringBinarySensorEntity(coordinator, description)
        for description in BINARY_SENSORS
    )


class HotSpringBinarySensorEntity(HotSpringEntity, BinarySensorEntity):
    """Defines a Hot Spring binary sensor entity."""

    entity_description: HotSpringBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HotSpringDataUpdateCoordinator,
        description: HotSpringBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)
