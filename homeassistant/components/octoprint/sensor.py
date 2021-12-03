"""Support for monitoring OctoPrint sensors."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from pyoctoprintapi import OctoprintJobInfo, OctoprintPrinterInfo

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OctoprintDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

JOB_PRINTING_STATES = ["Printing from SD", "Printing"]


def _is_printer_printing(printer: OctoprintPrinterInfo) -> bool:
    return (
        printer
        and printer.state
        and printer.state.flags
        and printer.state.flags.printing
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available OctoPrint binary sensors."""
    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    device_id = config_entry.unique_id

    assert device_id is not None

    entities: list[SensorEntity] = []
    if coordinator.data["printer"]:
        printer_info = coordinator.data["printer"]
        types = ["actual", "target"]
        for tool in printer_info.temperatures:
            for temp_type in types:
                entities.append(
                    OctoPrintTemperatureSensor(
                        coordinator,
                        tool.name,
                        temp_type,
                        device_id,
                    )
                )
    else:
        _LOGGER.error("Printer appears to be offline, skipping temperature sensors")

    entities.append(OctoPrintStatusSensor(coordinator, device_id))
    entities.append(OctoPrintJobPercentageSensor(coordinator, device_id))
    entities.append(OctoPrintEstimatedFinishTimeSensor(coordinator, device_id))
    entities.append(OctoPrintStartTimeSensor(coordinator, device_id))

    async_add_entities(entities)


class OctoPrintSensorBase(CoordinatorEntity, SensorEntity):
    """Representation of an OctoPrint sensor."""

    coordinator: OctoprintDataUpdateCoordinator

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        sensor_type: str,
        device_id: str,
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_name = f"OctoPrint {sensor_type}"
        self._attr_unique_id = f"{sensor_type}-{device_id}"

    @property
    def device_info(self):
        """Device info."""
        return self.coordinator.device_info


class OctoPrintStatusSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    _attr_icon = "mdi:printer-3d"

    def __init__(
        self, coordinator: OctoprintDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, "Current State", device_id)

    @property
    def native_value(self):
        """Return sensor state."""
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]
        if not printer:
            return None

        return printer.state.text

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data["printer"]


class OctoPrintJobPercentageSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:file-percent"

    def __init__(
        self, coordinator: OctoprintDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, "Job Percentage", device_id)

    @property
    def native_value(self):
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]
        if not job:
            return None

        if not (state := job.progress.completion):
            return 0

        return round(state, 2)


class OctoPrintEstimatedFinishTimeSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    _attr_device_class = DEVICE_CLASS_TIMESTAMP

    def __init__(
        self, coordinator: OctoprintDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, "Estimated Finish Time", device_id)

    @property
    def native_value(self) -> datetime | None:
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]
        if (
            not job
            or not job.progress.print_time_left
            or not _is_printer_printing(self.coordinator.data["printer"])
        ):
            return None

        read_time = self.coordinator.data["last_read_time"]

        return read_time + timedelta(seconds=job.progress.print_time_left)


class OctoPrintStartTimeSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    _attr_device_class = DEVICE_CLASS_TIMESTAMP

    def __init__(
        self, coordinator: OctoprintDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, "Start Time", device_id)

    @property
    def native_value(self) -> datetime | None:
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]

        if (
            not job
            or not job.progress.print_time
            or not _is_printer_printing(self.coordinator.data["printer"])
        ):
            return None

        read_time = self.coordinator.data["last_read_time"]

        return read_time - timedelta(seconds=job.progress.print_time)


class OctoPrintTemperatureSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        tool: str,
        temp_type: str,
        device_id: str,
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, f"{temp_type} {tool} temp", device_id)
        self._temp_type = temp_type
        self._api_tool = tool

    @property
    def native_value(self):
        """Return sensor state."""
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]
        if not printer:
            return None

        for temp in printer.temperatures:
            if temp.name == self._api_tool:
                val = (
                    temp.actual_temp
                    if self._temp_type == "actual"
                    else temp.target_temp
                )
                if val is None:
                    return None

                return round(val, 2)

        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data["printer"]
