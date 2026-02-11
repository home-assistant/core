"""Sensor platform for JVC Projector integration."""

from __future__ import annotations

from dataclasses import dataclass

from jvcprojector import Command, command as cmd

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity


@dataclass(frozen=True, kw_only=True)
class JvcProjectorSensorDescription(SensorEntityDescription):
    """Describes JVC Projector sensor entities."""

    command: type[Command]


SENSORS: tuple[JvcProjectorSensorDescription, ...] = (
    JvcProjectorSensorDescription(
        key="power",
        command=cmd.Power,
        device_class=SensorDeviceClass.ENUM,
    ),
    JvcProjectorSensorDescription(
        key="light_time",
        command=cmd.LightTime,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    JvcProjectorSensorDescription(
        key="color_depth",
        command=cmd.ColorDepth,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="color_space",
        command=cmd.ColorSpace,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="hdr",
        command=cmd.Hdr,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="hdr_processing",
        command=cmd.HdrProcessing,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="picture_mode",
        command=cmd.PictureMode,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JVCConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the JVC Projector platform from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        JvcProjectorSensorEntity(coordinator, description)
        for description in SENSORS
        if coordinator.supports(description.command)
    )


class JvcProjectorSensorEntity(JvcProjectorEntity, SensorEntity):
    """The entity class for JVC Projector integration."""

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        description: JvcProjectorSensorDescription,
    ) -> None:
        """Initialize the JVC Projector sensor."""
        super().__init__(coordinator, description.command)
        self.command: type[Command] = description.command

        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"

        self._options_map: dict[str, str] = {}
        if self.device_class == SensorDeviceClass.ENUM:
            self._options_map = coordinator.get_options_map(self.command.name)

    @property
    def options(self) -> list[str] | None:
        """Return a set of possible options."""
        if self.device_class == SensorDeviceClass.ENUM:
            return list(self._options_map.values())
        return None

    @property
    def native_value(self) -> str | None:
        """Return the native value."""
        value = self.coordinator.data.get(self.command.name)

        if value is None:
            return None

        if self.device_class == SensorDeviceClass.ENUM:
            return self._options_map.get(value)

        return value
