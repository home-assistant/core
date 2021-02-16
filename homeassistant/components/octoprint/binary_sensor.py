"""Support for monitoring OctoPrint binary sensors."""
import logging

from pyoctoprintapi import OctoprintPrinterInfo

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN as COMPONENT_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available OctoPrint binary sensors."""

    if discovery_info is None:
        return

    name = discovery_info["name"]
    base_url = discovery_info["base_url"]
    monitored_conditions = discovery_info["sensors"]
    coordinator: DataUpdateCoordinator = hass.data[COMPONENT_DOMAIN][base_url]

    devices = []
    if "Printing" in monitored_conditions:
        devices.append(OctoPrintPrintingBinarySensor(coordinator, name))

    if "Printing Error" in monitored_conditions:
        devices.append(OctoPrintPrintingErrorBinarySensor(coordinator, name))

    add_entities(devices, True)


class OctoPrintBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """Representation an OctoPrint binary sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_name: str,
        sensor_type: str,
    ):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator)
        self.sensor_name = sensor_name
        self._name = f"{sensor_name} {sensor_type}"
        self.sensor_type = sensor_type
        _LOGGER.debug("Created OctoPrint binary sensor %r", self)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return None

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        printer = self.coordinator.data["printer"]
        if not printer:
            return None

        return bool(self._get_flag_state(printer))

    def _get_flag_state(  # pylint: disable=no-self-use
        self, printer_info: OctoprintPrinterInfo
    ) -> bool or None:
        return None


class OctoPrintPrintingBinarySensor(OctoPrintBinarySensorBase):
    """Representation an OctoPrint binary sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Printing")

    def _get_flag_state(self, printer_info: OctoprintPrinterInfo) -> bool or None:
        return bool(printer_info.state.flags.printing)


class OctoPrintPrintingErrorBinarySensor(OctoPrintBinarySensorBase):
    """Representation an OctoPrint binary sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Printing Error")

    def _get_flag_state(self, printer_info: OctoprintPrinterInfo) -> bool or None:
        return bool(printer_info.state.flags.error)
