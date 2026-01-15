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
    """Describes JVC Projector select entities."""

    command: type[Command]


SENSORS: tuple[JvcProjectorSensorDescription, ...] = (
    JvcProjectorSensorDescription(
        key="power",
        command=cmd.Power,
        device_class=SensorDeviceClass.ENUM,
    ),
    JvcProjectorSensorDescription(
        key="model",
        command=cmd.ModelName,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JvcProjectorSensorDescription(
        key="source",
        command=cmd.Source,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JvcProjectorSensorDescription(
        key="light_time",
        command=cmd.LightTime,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JvcProjectorSensorDescription(
        key="color_depth",
        command=cmd.ColorDepth,
        device_class=SensorDeviceClass.ENUM,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JvcProjectorSensorDescription(
        key="color_space",
        command=cmd.ColorSpace,
        device_class=SensorDeviceClass.ENUM,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JvcProjectorSensorDescription(
        key="hdr",
        command=cmd.Hdr,
        device_class=SensorDeviceClass.ENUM,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JvcProjectorSensorDescription(
        key="hdr_processing",
        command=cmd.HdrProcessing,
        device_class=SensorDeviceClass.ENUM,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JvcProjectorSensorDescription(
        key="picture_mode",
        command=cmd.PictureMode,
        device_class=SensorDeviceClass.ENUM,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
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
        super().__init__(coordinator)

        self.entity_description = description
        self.command: type[Command] = description.command

        self._attr_translation_key = description.key
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"

        self._options_map: dict[str, str] = {}
        if self.device_class == SensorDeviceClass.ENUM:
            self._options_map = coordinator.get_options_map(self.command.name)

    @property
    def options(self) -> list[str]:
        """Return a set of possible options."""
        return list(self._options_map.values())

    @property
    def native_value(self) -> str | None:
        """Return the native value."""
        if value := self.coordinator.data.get(self.command.name):
            return self._options_map.get(value)
        return None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.coordinator.register(self.command)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        self.coordinator.unregister(self.command)
        await super().async_will_remove_from_hass()
