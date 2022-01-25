"""Add Flashforge sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ffpp.Printer import Printer, temperatures as Tool

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .data_update_coordinator import FlashForgeDataUpdateCoordinator


@dataclass
class FlashforgeSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description with added value fnc."""

    value_fnc: Callable[[Printer | Tool], str | int | None] | None = None


SENSORS: tuple[FlashforgeSensorEntityDescription, ...] = (
    FlashforgeSensorEntityDescription(
        key="status",
        icon="mdi:printer-3d",
        value_fnc=lambda printer: printer.machine_status,
    ),
    FlashforgeSensorEntityDescription(
        key="job_percentage",
        icon="mdi:file-percent",
        native_unit_of_measurement=PERCENTAGE,
        value_fnc=lambda printer: printer.print_percent,
    ),
)
TEMP_SENSORS: tuple[FlashforgeSensorEntityDescription, ...] = (
    FlashforgeSensorEntityDescription(
        key="_current",
        value_fnc=lambda tool: tool.now,
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FlashforgeSensorEntityDescription(
        key="_target",
        value_fnc=lambda tool: tool.target,
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available FlashForge sensors platform."""

    coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities: list[SensorEntity] = []

    if coordinator.printer.connected:
        # Loop all extruders and add current and target temp sensors.
        for i, tool in enumerate(coordinator.printer.extruder_tools):
            name = (
                f"extruder{i}"
                if len(coordinator.printer.extruder_tools) > 1
                else "extruder"
            )
            for description in TEMP_SENSORS:
                entities.append(
                    FlashForgeSensor(
                        coordinator=coordinator,
                        description=description,
                        name=name,
                        tool_name=tool.name,
                    )
                )

        # Loop all beds and add current and target temp sensors.
        for i, tool in enumerate(coordinator.printer.bed_tools):
            name = f"bed{i}" if len(coordinator.printer.bed_tools) > 1 else "bed"
            for description in TEMP_SENSORS:
                entities.append(
                    FlashForgeSensor(
                        coordinator=coordinator,
                        description=description,
                        name=name,
                        tool_name=tool.name,
                    )
                )

    for description in SENSORS:
        entities.append(
            FlashForgeSensor(
                coordinator=coordinator,
                description=description,
            )
        )

    async_add_entities(entities)


class FlashForgeSensor(CoordinatorEntity, SensorEntity):
    """Representation of an FlashForge sensor."""

    coordinator: FlashForgeDataUpdateCoordinator
    entity_description: FlashforgeSensorEntityDescription

    def __init__(
        self,
        coordinator: FlashForgeDataUpdateCoordinator,
        description: FlashforgeSensorEntityDescription,
        name: str = "",
        tool_name: str | None = None,
    ) -> None:
        """Initialize a new Flashforge sensor."""
        super().__init__(coordinator)
        self._device_id = coordinator.config_entry.unique_id
        self._attr_device_info = coordinator.device_info
        self.entity_description = description
        self._attr_name = f"{coordinator.printer.machine_name} {name.title()}{description.key.replace('_', ' ').title()}"
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{name}{description.key}"
        )

        self.tool_name = tool_name

    @property
    def native_value(self):
        """Return sensor state."""
        if self.tool_name:
            # If toolname is set we need to get that tool and pass it to the lambda.
            tool = self.coordinator.printer.extruder_tools.get(self.tool_name)
            if tool is None:
                tool = self.coordinator.printer.bed_tools.get(self.tool_name)
            return self.entity_description.value_fnc(tool)
        return self.entity_description.value_fnc(self.coordinator.printer)
