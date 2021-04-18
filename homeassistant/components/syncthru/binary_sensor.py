"""Support for Samsung Printers with SyncThru web interface."""

import logging

from pysyncthru import SyncThru, SyncthruState

from homeassistant.const import CONF_NAME
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
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

    printer = hass.data[DOMAIN][config_entry.entry_id]

    name = config_entry.data[CONF_NAME]
    devices = [
        SyncThruOnlineSensor(printer, name),
        SyncThruProblemSensor(printer, name),
    ]

    async_add_entities(devices, True)


class SyncThruBinarySensor(BinarySensorEntity):
    """Implementation of an abstract Samsung Printer binary sensor platform."""

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        self.syncthru: SyncThru = syncthru
        self._state = None
        self._name = name
        self._id_suffix = ""

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        serial = self.syncthru.serial_number()
        return serial + self._id_suffix if serial else super().unique_id

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

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._id_suffix = "_online"

    def is_on(self):
        """Whether the printer is online."""
        return self._state

    def device_class(self):
        """Class of the sensor."""
        return DEVICE_CLASS_CONNECTIVITY

    async def async_update(self):
        """Get the latest data from SyncThru and update the state."""
        self._state = self.syncthru.is_online()


class SyncThruProblemSensor(SyncThruBinarySensor):
    """Implementation of a sensor that checks whether the printer works correctly."""

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._id_suffix = "_problem"

    def is_on(self):
        """Whether there is a problem with the printer."""
        return self._state

    def device_class(self):
        """Class of the sensor."""
        return DEVICE_CLASS_PROBLEM

    async def async_update(self):
        """Get the latest data from SyncThru and update the state."""
        self._state = SYNCTHRU_STATE_PROBLEM[self.syncthru.device_status()]
