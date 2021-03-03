"""Support for monitoring OctoPrint sensors."""
from datetime import timedelta
import logging

from pyoctoprintapi import OctoprintJobInfo, OctoprintPrinterInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN as COMPONENT_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up the available OctoPrint binary sensors."""
    coordinator: DataUpdateCoordinator = hass.data[COMPONENT_DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    device_id: str = hass.data[COMPONENT_DOMAIN][config_entry.entry_id]["device_id"]
    entities = []
    sensor_name = config_entry.data[CONF_NAME]
    if coordinator.data["printer"]:
        printer_info = coordinator.data["printer"]
        types = ["actual", "target"]
        for tool in printer_info.temperatures:
            for temp_type in types:
                entities.append(
                    OctoPrintTemperatureSensor(
                        coordinator, sensor_name, tool.name, temp_type, device_id
                    )
                )
    else:
        _LOGGER.error("Printer appears to be offline, skipping temperature sensors")

    entities.append(OctoPrintStatusSensor(coordinator, sensor_name, device_id))
    entities.append(OctoPrintJobPercentageSensor(coordinator, sensor_name, device_id))
    entities.append(
        OctoPrintEstimatedFinishTimeSensor(coordinator, sensor_name, device_id)
    )
    entities.append(OctoPrintStartTimeSensor(coordinator, sensor_name, device_id))

    async_add_entities(entities, True)
    return True


class OctoPrintSensorBase(CoordinatorEntity, Entity):
    """Representation of an OctoPrint sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_name: str,
        sensor_type: str,
        device_id: str,
    ):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator)
        self._state = None
        self._sensor_name = sensor_name
        self._sensor_type = sensor_type
        self._name = f"{sensor_name} {sensor_type}"
        self._device_id = device_id

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(COMPONENT_DOMAIN, self._device_id)},
            "name": self._sensor_name,
        }

    @property
    def unique_id(self):
        """Return a unique id."""
        return f"{self._sensor_type}-{self._device_id}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name


class OctoPrintStatusSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sensor_name: str, device_id: str
    ):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Current State", device_id)

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

    def __init__(
        self, coordinator: DataUpdateCoordinator, sensor_name: str, device_id: str
    ):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Job Percentage", device_id)

    @property
    def state(self):
        """Return sensor state."""
        job: OctoprintJobInfo = self.coordinator.data["job"]
        if not job:
            return None

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


class OctoPrintEstimatedFinishTimeSensor(OctoPrintSensorBase):
    """Representation of an OctoPrint sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sensor_name: str, device_id: str
    ):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Estimated Finish Time", device_id)

    @property
    def state(self):
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

    def __init__(
        self, coordinator: DataUpdateCoordinator, sensor_name: str, device_id: str
    ):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Start Time", device_id)

    @property
    def state(self):
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
        device_id: str,
    ):
        """Initialize a new OctoPrint sensor."""
        super().__init__(
            coordinator, sensor_name, f"{temp_type} {tool} temp", device_id
        )
        self._temp_type = temp_type
        self._api_tool = tool
        self._state = 0

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return TEMP_CELSIUS

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def state(self):
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
