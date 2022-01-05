"""Add FlashForge sensors."""
from __future__ import annotations

from ffpp.Printer import Printer, ToolHandler

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .data_update_coordinator import FlashForgeDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available FlashForge sensors platform."""

    # This is called after async_setup_entry in __init__.py

    # Get coordinator and unique id.
    coordinator: FlashForgeDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    printer: Printer = hass.data[DOMAIN][config_entry.entry_id]["printer"]
    device_id = config_entry.unique_id or ""

    # Create a list of your sensors on this platform.
    entities: list[SensorEntity] = []

    # Create temperature sensors.
    if printer.connected:
        types = ["now", "target"]
        for tool in printer.extruder_tools:
            for temp_type in types:
                entities.append(
                    FlashForgeTemperatureSensor(
                        coordinator,
                        tool.name,
                        temp_type,
                        printer.extruder_tools,
                        device_id,
                    )
                )
        for tool in printer.bed_tools:
            for temp_type in types:
                entities.append(
                    FlashForgeTemperatureSensor(
                        coordinator,
                        tool.name,
                        temp_type,
                        printer.bed_tools,
                        device_id,
                    )
                )

    entities.append(FlashForgeStatusSensor(coordinator, device_id))
    entities.append(FlashForgeJobPercentageSensor(coordinator, device_id))

    async_add_entities(entities)


class FlashForgeSensorBase(CoordinatorEntity, SensorEntity):
    """Representation of an FlashForge sensor."""

    coordinator: FlashForgeDataUpdateCoordinator

    def __init__(
        self,
        coordinator: FlashForgeDataUpdateCoordinator,
        sensor_type: str,
        device_id: str,
    ) -> None:
        """Initialize a new FlashForge sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"{DEFAULT_NAME} {sensor_type}"
        self._attr_unique_id = f"{sensor_type}-{device_id}"

    @property
    def device_info(self):
        """Device info."""
        return self.coordinator.device_info


class FlashForgeStatusSensor(FlashForgeSensorBase):
    """Representation of an FlashForge sensor."""

    _attr_icon = "mdi:printer-3d"

    def __init__(
        self, coordinator: FlashForgeDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a new FlashForge sensor."""
        super().__init__(coordinator, "Current State", device_id)

    @property
    def native_value(self):
        """Return sensor state."""
        status: str = self.coordinator.printer.status
        return status

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.printer.status


class FlashForgeJobPercentageSensor(FlashForgeSensorBase):
    """Representation of an FlashForge sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:file-percent"

    def __init__(
        self, coordinator: FlashForgeDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a new FlashForge sensor."""
        super().__init__(coordinator, "Job Percentage", device_id)

    @property
    def native_value(self):
        """Return sensor state."""
        percent: str = self.coordinator.printer.print_percent

        return percent

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.printer.print_percent
        )


class FlashForgeTemperatureSensor(FlashForgeSensorBase):
    """Representation of an FlashForge sensor."""

    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(
        self,
        coordinator: FlashForgeDataUpdateCoordinator,
        tool_name: str,
        temp_type: str,
        tool_handler: ToolHandler,
        device_id: str,
    ) -> None:
        """Initialize a new FlashForge sensor."""
        super().__init__(coordinator, f"{tool_name} {temp_type} temp", device_id)
        self._temp_type = temp_type
        self._tool_name = tool_name
        self.tool_handler = tool_handler

    @property
    def native_value(self):
        """Return sensor state."""
        tool = self.tool_handler.get(self._tool_name)

        temp = tool.now
        if self._temp_type == "target":
            temp = tool.target

        return temp

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.tool_handler.get(
            self._tool_name
        )
