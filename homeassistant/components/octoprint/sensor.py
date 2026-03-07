"""Support for monitoring OctoPrint sensors."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from pyoctoprintapi import OctoprintJobInfo, OctoprintPrinterInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfInformation, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OctoprintDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the available OctoPrint sensors."""
    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    device_id = config_entry.unique_id

    assert device_id is not None

    known_tools = set()

    @callback
    def async_add_tool_sensors() -> None:
        if not coordinator.data["printer"]:
            return

        new_tools: list[OctoPrintTemperatureSensor] = []
        for tool in [
            tool
            for tool in coordinator.data["printer"].temperatures
            if tool.name not in known_tools
        ]:
            assert device_id is not None
            known_tools.add(tool.name)
            new_tools.extend(
                OctoPrintTemperatureSensor(
                    coordinator,
                    tool.name,
                    temp_type,
                    device_id,
                )
                for temp_type in ("actual", "target")
            )
        async_add_entities(new_tools)

    config_entry.async_on_unload(coordinator.async_add_listener(async_add_tool_sensors))

    if coordinator.data["printer"]:
        async_add_tool_sensors()

    entities: list[SensorEntity] = [
        OctoPrintStatusSensor(coordinator, device_id),
        OctoPrintJobPercentageSensor(coordinator, device_id),
        OctoPrintEstimatedFinishTimeSensor(coordinator, device_id),
        OctoPrintStartTimeSensor(coordinator, device_id),
        OctoPrintFileNameSensor(coordinator, device_id),
        OctoPrintFileSizeSensor(coordinator, device_id),
    ]

    async_add_entities(entities)


class OctoPrintSensorBase(
    CoordinatorEntity[OctoprintDataUpdateCoordinator], SensorEntity
):
    """Representation of an OctoPrint sensor."""

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
        self._attr_device_info = coordinator.device_info


# Map the strings returned by the OctoPrint API back into values based on the underlying OctoPrint constants.
# See octoprint.util.comm.MahcineCom.getStateString():
# https://github.com/OctoPrint/OctoPrint/blob/7e7d418dac467e308b24c669a03e8b4256f04b45/src/octoprint/util/comm.py#L965
_API_STATE_VALUE = {
    "Opening serial connection": "open_serial",
    "Detecting serial connection": "detect_serial",
    "Connecting": "connecting",
    "Operational": "operational",
    "Starting print from SD": "starting_sd",
    "Starting to send file to SD": "starting_streaming",
    "Starting": "starting",
    "Printing from SD": "printing_sd",
    "Sending file to SD": "printing_streaming",
    "Printing": "printing",
    "Cancelling": "cancelling",
    "Pausing": "pausing",
    "Paused": "paused",
    "Resuming": "resuming",
    "Finishing": "finishing",
    "Offline": "offline",
    "Error": "error",
    "Offline after error": "offline_after_error",
    "Transferring file to SD": "transferring_file",
}


class OctoPrintStatusSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint status sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(_API_STATE_VALUE.values())
    _attr_translation_key = "status"

    def __init__(
        self, coordinator: OctoprintDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, "Current State", device_id)

    @property
    def native_value(self):
        """Return sensor state."""

        # Get printer data from the coordinator
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]
        if not printer:
            return None

        # Translate the string from the API into an internal state value, or return None (Unknown) if no match
        return _API_STATE_VALUE.get(printer.state.text)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data["printer"]


class OctoPrintJobPercentageSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint job percentage sensor."""

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
    """Representation of an OctoPrint estimated finish time sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-end"

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

        return (read_time + timedelta(seconds=job.progress.print_time_left)).replace(
            second=0
        )


class OctoPrintStartTimeSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint start time sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-start"

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

        return (read_time - timedelta(seconds=job.progress.print_time)).replace(
            second=0
        )


class OctoPrintTemperatureSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint temperature sensor."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:printer-3d-nozzle-heat"

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


class OctoPrintFileNameSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint file name sensor."""

    _attr_translation_key = "file_name"

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, "Current File", device_id)

    @property
    def native_value(self) -> str | None:
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]

        return job.job.file.name or None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        job: OctoprintJobInfo = self.coordinator.data["job"]
        return job and job.job.file.name


class OctoPrintFileSizeSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint file size sensor."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_suggested_unit_of_measurement = UnitOfInformation.MEGABYTES

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, "Current File Size", device_id)

    @property
    def native_value(self) -> int | None:
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]

        return job.job.file.size or None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        job: OctoprintJobInfo = self.coordinator.data["job"]
        return job and job.job.file.size
