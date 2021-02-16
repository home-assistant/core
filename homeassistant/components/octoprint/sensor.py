"""Support for monitoring OctoPrint sensors."""
import logging

from pyoctoprintapi import OctoprintJobInfo, OctoprintPrinterInfo

from homeassistant.const import PERCENTAGE, TEMP_CELSIUS, TIME_SECONDS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import CONF_BED, CONF_NUMBER_OF_TOOLS, DOMAIN as COMPONENT_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available OctoPrint sensors."""
    if discovery_info is None:
        return

    name = discovery_info["name"]
    base_url = discovery_info["base_url"]
    monitored_conditions = discovery_info["sensors"]
    number_of_tools = discovery_info[CONF_NUMBER_OF_TOOLS]
    bed = discovery_info[CONF_BED]
    coordinator: DataUpdateCoordinator = hass.data[COMPONENT_DOMAIN][base_url]
    tools = []
    if coordinator.data["printer"]:
        tools = [tool.name for tool in coordinator.data["printer"].temperatures]
    else:
        if number_of_tools > 0:
            for tool_number in range(0, number_of_tools):
                tools.append(f"tool{tool_number!s}")
        if bed:
            tools.append("bed")

    devices = []
    types = ["actual", "target"]

    if "Temperatures" in monitored_conditions and tools:
        for tool in tools:
            for temp_type in types:
                devices.append(
                    OctoPrintTemperatureSensor(coordinator, name, tool, temp_type)
                )

    if "Current State" in monitored_conditions:
        devices.append(OctoPrintStatusSensor(coordinator, name))
    if "Job Percentage" in monitored_conditions:
        devices.append(OctoPrintJobPercentageSensor(coordinator, name))
    if "Time Remaining" in monitored_conditions:
        devices.append(OctoPrintTimeRemainingSensor(coordinator, name))
    if "Time Elapsed" in monitored_conditions:
        devices.append(OctoPrintTimeRemainingSensor(coordinator, name))

    add_entities(devices, True)


class OctoPrintSensorBase(CoordinatorEntity, Entity):
    """Representation of an OctoPrint sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_name: str,
        sensor_type: str,
    ):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator)
        self._state = None
        self._sensor_name = sensor_name
        self._name = f"{sensor_name} {sensor_type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name


class OctoPrintStatusSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Current State")

    @property
    def state(self):
        """Return sensor state."""
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]
        if not printer:
            return None

        return printer.state.text

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:printer-3d"


class OctoPrintJobPercentageSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Job Percentage")

    @property
    def state(self):
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]
        if not job:
            return 0

        state = job.progress.completion
        if not state:
            return 0

        return round(state, 2)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return PERCENTAGE

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:file-percent"


class OctoPrintTimeRemainingSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Time Remaining")

    @property
    def state(self):
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]
        if not job:
            return None

        return job.progress.print_time_left

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return TIME_SECONDS

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:clock-start"


class OctoPrintTimeElapsedSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Time Elapsed")

    @property
    def state(self):
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]
        if not job:
            return None

        return job.progress.print_time

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return TIME_SECONDS

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:clock-end"


class OctoPrintTemperatureSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_name: str,
        tool: str,
        temp_type: str,
    ):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, f"{temp_type} {tool} temp")
        self._temp_type = temp_type
        self._api_tool = tool
        self._state = 0

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return TEMP_CELSIUS

    @property
    def state(self):
        """Return sensor state."""
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]
        if not printer:
            return None

        for temp in printer.temperatures:
            if temp.name == self._api_tool:
                return (
                    temp.actual_temp
                    if self._temp_type == "actual"
                    else temp.target_temp
                )

        return None
