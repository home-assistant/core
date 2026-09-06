"""Sensor platform for JVC Projector integration."""

from dataclasses import dataclass
from typing import override

from jvcprojector import Command, command as cmd

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
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
    name: str | None = None


SENSORS: tuple[JvcProjectorSensorDescription, ...] = (
    JvcProjectorSensorDescription(
        key="power",
        name="Power",
        command=cmd.Power,
        device_class=SensorDeviceClass.ENUM,
    ),
    JvcProjectorSensorDescription(
        key="light_time",
        name="Light Time",
        command=cmd.LightTime,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    JvcProjectorSensorDescription(
        key="software_version",
        name="Software Version",
        command=cmd.Version,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="color_depth",
        name="Color Depth",
        command=cmd.ColorDepth,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="color_space",
        name="Color Space",
        command=cmd.ColorSpace,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="hdr",
        name="HDR",
        command=cmd.Hdr,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="resolution",
        name="Resolution",
        command=cmd.Source,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="colorimetry",
        name="Colorimetry",
        command=cmd.Colorimetry,
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSensorDescription(
        key="link_rate",
        name="Link Rate",
        command=cmd.LinkRate,
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

    entities: list[JvcProjectorSensorEntity] = []
    for description in SENSORS:
        if not coordinator.supports(description.command):
            continue
        entities.append(JvcProjectorSensorEntity(coordinator, description))

    async_add_entities(entities)


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
        if description.name:
            self._attr_name = description.name

        self._options_map: dict[str, str] = {}
        if self.device_class == SensorDeviceClass.ENUM:
            self._options_map = coordinator.get_options_map(self.command.name)

    @property
    @override
    def options(self) -> list[str] | None:
        """Return a set of possible options."""
        if self.device_class == SensorDeviceClass.ENUM:
            return list(self._options_map.values())
        return None

    @property
    @override
    def native_value(self) -> str | None:
        """Return the native value."""
        value = self.coordinator.data.get(self.command.name)

        if value is None:
            return None

        # Format software version from 0301 to 3.01
        if self.entity_description.key == "software_version" and value:
            try:
                # Remove "PJ" suffix if present
                value = value.removesuffix("PJ")
                # Pad to 4 digits
                value = value.zfill(4)
                # Format as major.minor.patch
                major = str(int(value[0:2]))
                minor = str(int(value[2]))
                patch = str(int(value[3]))
                return f"{major}.{minor}.{patch}"
            except (ValueError, IndexError):
                return value

        if self.device_class == SensorDeviceClass.ENUM:
            return self._options_map.get(value)

        return value
