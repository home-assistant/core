"""Binary sensor platform for Nord Pool integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NordPoolConfigEntry
from .const import CONF_AREAS
from .coordinator import NordPoolDataUpdateCoordinator
from .entity import NordpoolBaseEntity

PARALLEL_UPDATES = 0


def get_tomorrow_price_available(
    entity: NordpoolPriceBinarySensor,
) -> bool:
    """Return tomorrow price availability."""
    data = entity.coordinator.get_data_tomorrow()
    return bool(data and data.entries and entity.area in data.entries[0].entry)


@dataclass(frozen=True, kw_only=True)
class NordpoolBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Nord Pool binary sensor entity."""

    value_fn: Callable[[NordpoolPriceBinarySensor], bool | None]


BINARY_SENSOR_TYPES: tuple[NordpoolBinarySensorEntityDescription, ...] = (
    NordpoolBinarySensorEntityDescription(
        key="tomorrow_price_available",
        translation_key="tomorrow_price_available",
        value_fn=get_tomorrow_price_available,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NordPoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Nord Pool binary sensor platform."""

    coordinator = entry.runtime_data
    areas = coordinator.config_entry.data[CONF_AREAS]

    async_add_entities(
        NordpoolPriceBinarySensor(coordinator, description, area)
        for description in BINARY_SENSOR_TYPES
        for area in areas
    )


class NordpoolPriceBinarySensor(NordpoolBaseEntity, BinarySensorEntity):
    """Representation of a Nord Pool binary sensor."""

    entity_description: NordpoolBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NordPoolDataUpdateCoordinator,
        entity_description: NordpoolBinarySensorEntityDescription,
        area: str,
    ) -> None:
        """Initiate Nord Pool binary sensor."""
        super().__init__(coordinator, entity_description, area)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self)
