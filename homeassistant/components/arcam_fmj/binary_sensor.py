"""Arcam binary sensors for incoming stream info."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from arcam.fmj.state import State

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ArcamFmjConfigEntry
from .const import DOMAIN
from .coordinator import ArcamFmjCoordinator


@dataclass(frozen=True, kw_only=True)
class ArcamFmjBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Arcam FMJ binary sensor entity."""

    value_fn: Callable[[State], bool | None]


BINARY_SENSORS: tuple[ArcamFmjBinarySensorEntityDescription, ...] = (
    ArcamFmjBinarySensorEntityDescription(
        key="incoming_video_interlaced",
        translation_key="incoming_video_interlaced",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: getattr(
            state.get_incoming_video_parameters(), "interlaced", None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ArcamFmjConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Arcam FMJ binary sensors from a config entry."""
    coordinators = config_entry.runtime_data
    uuid = config_entry.unique_id or config_entry.entry_id
    device_info = DeviceInfo(
        identifiers={(DOMAIN, uuid)},
        manufacturer="Arcam",
        model="Arcam FMJ AVR",
        name=config_entry.title,
    )

    entities: list[ArcamFmjBinarySensorEntity] = []
    for zone in (1, 2):
        coordinator = coordinators[zone]
        entities.extend(
            ArcamFmjBinarySensorEntity(
                device_info=device_info,
                uuid=uuid,
                coordinator=coordinator,
                description=description,
            )
            for description in BINARY_SENSORS
        )
    async_add_entities(entities)


class ArcamFmjBinarySensorEntity(
    CoordinatorEntity[ArcamFmjCoordinator], BinarySensorEntity
):
    """Representation of an Arcam FMJ binary sensor."""

    entity_description: ArcamFmjBinarySensorEntityDescription
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        device_info: DeviceInfo,
        uuid: str,
        coordinator: ArcamFmjCoordinator,
        description: ArcamFmjBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._state = coordinator.state
        self._attr_unique_id = f"{uuid}-{self._state.zn}-{description.key}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"zone": str(self._state.zn)}

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor value."""
        return self.entity_description.value_fn(self._state)
