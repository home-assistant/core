"""Support for Balboa Spa binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pybalboa import SpaClient

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BalboaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa's binary sensors."""
    spa: SpaClient = hass.data[DOMAIN][entry.entry_id]
    entities = [
        BalboaBinarySensorEntity(spa, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    if spa.circulation_pump is not None:
        entities.append(BalboaBinarySensorEntity(spa, CIRCULATION_PUMP_DESCRIPTION))
    async_add_entities(entities)


@dataclass(frozen=True)
class BalboaBinarySensorEntityDescriptionMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[SpaClient], bool]
    on_off_icons: tuple[str, str]


@dataclass(frozen=True)
class BalboaBinarySensorEntityDescription(
    BinarySensorEntityDescription, BalboaBinarySensorEntityDescriptionMixin
):
    """A class that describes Balboa binary sensor entities."""


FILTER_CYCLE_ICONS = ("mdi:sync", "mdi:sync-off")
BINARY_SENSOR_DESCRIPTIONS = (
    BalboaBinarySensorEntityDescription(
        key="Filter1",
        translation_key="filter_1",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda spa: spa.filter_cycle_1_running,
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
    BalboaBinarySensorEntityDescription(
        key="Filter2",
        translation_key="filter_2",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda spa: spa.filter_cycle_2_running,
        on_off_icons=FILTER_CYCLE_ICONS,
    ),
)
CIRCULATION_PUMP_DESCRIPTION = BalboaBinarySensorEntityDescription(
    key="Circ Pump",
    translation_key="circ_pump",
    device_class=BinarySensorDeviceClass.RUNNING,
    is_on_fn=lambda spa: (pump := spa.circulation_pump) is not None and pump.state > 0,
    on_off_icons=("mdi:pump", "mdi:pump-off"),
)


class BalboaBinarySensorEntity(BalboaEntity, BinarySensorEntity):
    """Representation of a Balboa Spa binary sensor entity."""

    entity_description: BalboaBinarySensorEntityDescription

    def __init__(
        self, spa: SpaClient, description: BalboaBinarySensorEntityDescription
    ) -> None:
        """Initialize a Balboa binary sensor entity."""
        super().__init__(spa, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self._client)

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        icons = self.entity_description.on_off_icons
        return icons[0] if self.is_on else icons[1]
