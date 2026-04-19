"""NINA sensor platform."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_MESSAGE_SLOTS, CONF_REGIONS, SENSOR_SUFFIXES, SEVERITY_VALUES
from .coordinator import NinaConfigEntry, NINADataUpdateCoordinator, NinaWarningData
from .entity import NinaEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NinaSensorEntityDescription(SensorEntityDescription):
    """Describes NINA sensor entity."""

    value_fn: Callable[[NinaWarningData], str | datetime | None]


SENSOR_TYPES: tuple[NinaSensorEntityDescription, ...] = (
    NinaSensorEntityDescription(
        key=SENSOR_SUFFIXES[0],
        translation_key="headline",
        value_fn=lambda data: data.headline,
    ),
    NinaSensorEntityDescription(
        key=SENSOR_SUFFIXES[1],
        translation_key="sender",
        value_fn=lambda data: data.sender,
    ),
    NinaSensorEntityDescription(
        key=SENSOR_SUFFIXES[2],
        options=SEVERITY_VALUES,
        device_class=SensorDeviceClass.ENUM,
        translation_key="severity",
        value_fn=lambda data: (
            data.severity.lower() if data.severity is not None else None
        ),
    ),
    NinaSensorEntityDescription(
        key=SENSOR_SUFFIXES[3],
        translation_key="affected_areas",
        value_fn=lambda data: data.affected_areas_short,
    ),
    NinaSensorEntityDescription(
        key=SENSOR_SUFFIXES[4],
        translation_key="more_info_url",
        value_fn=lambda data: data.more_info_url,
    ),
    NinaSensorEntityDescription(
        key=SENSOR_SUFFIXES[5],
        translation_key="sent",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.sent,
    ),
    NinaSensorEntityDescription(
        key=SENSOR_SUFFIXES[6],
        translation_key="start",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.start,
    ),
    NinaSensorEntityDescription(
        key=SENSOR_SUFFIXES[7],
        translation_key="expires",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.expires,
    ),
)


def create_sensors_for_warning(
    coordinator: NINADataUpdateCoordinator, region: str, region_name: str, slot_id: int
) -> Sequence[NinaSensor]:
    """Create sensors for a warning."""
    return [
        NinaSensor(
            coordinator,
            region,
            region_name,
            slot_id,
            description,
        )
        for description in SENSOR_TYPES
    ]


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: NinaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NINA sensor platform."""

    coordinator = config_entry.runtime_data

    regions: dict[str, str] = config_entry.data[CONF_REGIONS]
    message_slots: int = config_entry.data[CONF_MESSAGE_SLOTS]

    entities = [
        create_sensors_for_warning(coordinator, ent, regions[ent], i + 1)
        for ent in coordinator.data
        for i in range(message_slots)
    ]

    async_add_entities(
        [entity for slot_entities in entities for entity in slot_entities]
    )


class NinaSensor(NinaEntity, SensorEntity):
    """Representation of a NINA sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    entity_description: NinaSensorEntityDescription

    def __init__(
        self,
        coordinator: NINADataUpdateCoordinator,
        region: str,
        region_name: str,
        slot_id: int,
        description: NinaSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, region, region_name, slot_id)

        self.entity_description = description

        self._attr_unique_id = f"{region}-{slot_id}-{self.entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._get_active_warnings_count() <= self._warning_index:
            return False

        return self._get_warning_data().is_valid and super().available

    @property
    def native_value(self) -> str | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._get_warning_data())
