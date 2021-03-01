"""Support for monitoring OctoPrint sensors."""
from datetime import timedelta
import logging

from pyoctoprintapi import OctoprintJobInfo, OctoprintPrinterInfo

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import CONF_BED, CONF_NUMBER_OF_TOOLS, DOMAIN as COMPONENT_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
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
            for tool_number in range(number_of_tools):
                tools.append(f"tool{tool_number!s}")
        if bed:
            tools.append("bed")

    entities = []
    types = ["actual", "target"]

    if "Temperatures" in monitored_conditions and tools:
        for tool in tools:
            for temp_type in types:
                entities.append(
                    OctoPrintTemperatureSensor(coordinator, name, tool, temp_type)
                )

    if "Current State" in monitored_conditions:
        entities.append(OctoPrintStatusSensor(coordinator, name))
    if "Job Percentage" in monitored_conditions:
        entities.append(OctoPrintJobPercentageSensor(coordinator, name))
    if "Time Remaining" in monitored_conditions:
        entities.append(OctoPrintEstimatedFinishTimeSensor(coordinator, name))
    if "Time Elapsed" in monitored_conditions:
        entities.append(OctoPrintStartTimeSensor(coordinator, name))

    async_add_entities(entities, True)


class OctoPrintSensorBase(CoordinatorEntity, SensorEntity):
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
    def native_value(self):
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
    def native_value(self):
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]
        if not job:
            return None

        state = job.progress.completion
        if not state:
            return 0

        return round(state, 2)

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return PERCENTAGE

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:file-percent"


class OctoPrintEstimatedFinishTimeSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Estimated Finish Time")

    @property
    def native_value(self):
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]
        if not job or not job.progress.print_time_left:
            return None

        read_time = self.coordinator.data["last_read_time"]

        return (read_time + timedelta(seconds=job.progress.print_time_left)).isoformat()

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TIMESTAMP


class OctoPrintStartTimeSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Start Time")

    @property
    def native_value(self):
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]

        if not job or not job.progress.print_time:
            return None

        read_time = self.coordinator.data["last_read_time"]

        return (read_time - timedelta(seconds=job.progress.print_time)).isoformat()

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TIMESTAMP


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
        self._attr_state_class = STATE_CLASS_MEASUREMENT

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return TEMP_CELSIUS

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def native_value(self):
        """Return sensor state."""
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]
        if not printer:
            return None

        for temp in printer.temperatures:
            if temp.name == self._api_tool:
                return round(
                    temp.actual_temp
                    if self._temp_type == "actual"
                    else temp.target_temp,
                    2,
                )

        return None
