"""Binary sensor platform for the LoJack integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from lojack_api.models import Location

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LoJackConfigEntry
from .const import MOVEMENT_SPEED_THRESHOLD
from .entity import LoJackEntity

PARALLEL_UPDATES = 0


def _is_connected(data: Location) -> bool:
    """Return True if the vehicle has reported usable location data."""
    return data.timestamp is not None or (
        data.latitude is not None and data.longitude is not None
    )


def _is_moving(data: Location) -> bool | None:
    """Return True if the vehicle is moving."""
    if data.speed is None:
        return None
    return data.speed > MOVEMENT_SPEED_THRESHOLD


@dataclass(frozen=True, kw_only=True)
class LoJackBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes LoJack binary sensor."""

    value_fn: Callable[[Location], bool | None]


BINARY_SENSORS: tuple[LoJackBinarySensorEntityDescription, ...] = (
    LoJackBinarySensorEntityDescription(
        key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_is_connected,
    ),
    LoJackBinarySensorEntityDescription(
        key="moving",
        device_class=BinarySensorDeviceClass.MOVING,
        value_fn=_is_moving,
    ),
)


class LoJackBinarySensor(LoJackEntity, BinarySensorEntity):
    """Representation of a LoJack binary sensor."""

    entity_description: LoJackBinarySensorEntityDescription

    @override
    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor value from the latest location data."""
        location = self.coordinator.data
        return self.entity_description.value_fn(location)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LoJack binary sensors from a config entry."""
    async_add_entities(
        LoJackBinarySensor(coordinator, description)
        for coordinator in entry.runtime_data.coordinators
        for description in BINARY_SENSORS
    )
