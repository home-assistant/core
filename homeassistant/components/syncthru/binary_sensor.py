"""Support for Samsung Printers with SyncThru web interface."""

import logging

from pysyncthru import SyncThru, SyncthruState

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import device_identifiers
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SYNCTHRU_STATE_PROBLEM = {
    SyncthruState.INVALID: True,
    SyncthruState.OFFLINE: None,
    SyncthruState.NORMAL: False,
    SyncthruState.UNKNOWN: True,
    SyncthruState.WARNING: True,
    SyncthruState.TESTING: False,
    SyncthruState.ERROR: True,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up from config entry."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    name = config_entry.data[CONF_NAME]
    entities = [
        SyncThruOnlineSensor(coordinator, name),
        SyncThruProblemSensor(coordinator, name),
    ]

    async_add_entities(entities)


class SyncThruBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Implementation of an abstract Samsung Printer binary sensor platform."""

    def __init__(self, coordinator, name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.syncthru: SyncThru = coordinator.data
        self._name = name
        self._id_suffix = ""

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        serial = self.syncthru.serial_number()
        return f"{serial}{self._id_suffix}" if serial else None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": device_identifiers(self.syncthru)}


class SyncThruOnlineSensor(SyncThruBinarySensor):
    """Implementation of a sensor that checks whether is turned on/online."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._id_suffix = "_online"

    @property
    def is_on(self):
        """Set the state to whether the printer is online."""
        return self.syncthru.is_online()


class SyncThruProblemSensor(SyncThruBinarySensor):
    """Implementation of a sensor that checks whether the printer works correctly."""

    _attr_device_class = DEVICE_CLASS_PROBLEM

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._id_suffix = "_problem"

    @property
    def is_on(self):
        """Set the state to whether there is a problem with the printer."""
        return SYNCTHRU_STATE_PROBLEM[self.syncthru.device_status()]
