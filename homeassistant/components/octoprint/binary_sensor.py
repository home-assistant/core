"""Support for monitoring OctoPrint binary sensors."""
from abc import abstractmethod
import logging
from typing import Optional

from pyoctoprintapi import OctoprintPrinterInfo

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN as COMPONENT_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up the available OctoPrint binary sensors."""
    coordinator = hass.data[COMPONENT_DOMAIN][config_entry.entry_id]["coordinator"]

    entities = [
        OctoPrintPrintingBinarySensor(coordinator, config_entry.data[CONF_NAME]),
        OctoPrintPrintingErrorBinarySensor(coordinator, config_entry.data[CONF_NAME]),
    ]

    async_add_entities(entities, True)
    return True


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
    def is_on(self):
        """Return true if binary sensor is on."""
        printer = self.coordinator.data["printer"]
        if not printer:
            return None

        return bool(self._get_flag_state(printer))

    @abstractmethod
    def _get_flag_state(self, printer_info: OctoprintPrinterInfo) -> Optional[bool]:
        """Return the value of the sensor flag."""


class OctoPrintPrintingBinarySensor(OctoPrintBinarySensorBase):
    """Representation an OctoPrint binary sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Printing")

    def _get_flag_state(self, printer_info: OctoprintPrinterInfo) -> Optional[bool]:
        return bool(printer_info.state.flags.printing)


class OctoPrintPrintingErrorBinarySensor(OctoPrintBinarySensorBase):
    """Representation an OctoPrint binary sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, sensor_name: str):
        """Initialize a new OctoPrint sensor."""
        super().__init__(coordinator, sensor_name, "Printing Error")

    def _get_flag_state(self, printer_info: OctoprintPrinterInfo) -> Optional[bool]:
        return bool(printer_info.state.flags.error)
