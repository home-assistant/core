"""Support for Samsung Printers with SyncThru web interface."""

from __future__ import annotations

from pysyncthru import SyncThru, SyncthruState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import device_identifiers
from .const import DOMAIN

SYNCTHRU_STATE_PROBLEM = {
    SyncthruState.INVALID: True,
    SyncthruState.OFFLINE: None,
    SyncthruState.NORMAL: False,
    SyncthruState.UNKNOWN: True,
    SyncthruState.WARNING: True,
    SyncthruState.TESTING: False,
    SyncthruState.ERROR: True,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up from config entry."""

    coordinator: DataUpdateCoordinator[SyncThru] = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    name: str = config_entry.data[CONF_NAME]
    entities = [
        SyncThruOnlineSensor(coordinator, name),
        SyncThruProblemSensor(coordinator, name),
    ]

    async_add_entities(entities)


class SyncThruBinarySensor(
    CoordinatorEntity[DataUpdateCoordinator[SyncThru]], BinarySensorEntity
):
    """Implementation of an abstract Samsung Printer binary sensor platform."""

    def __init__(self, coordinator: DataUpdateCoordinator[SyncThru], name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.syncthru = coordinator.data
        self._attr_name = name
        self._id_suffix = ""

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        serial = self.syncthru.serial_number()
        return f"{serial}{self._id_suffix}" if serial else None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information."""
        if (identifiers := device_identifiers(self.syncthru)) is None:
            return None
        return DeviceInfo(
            identifiers=identifiers,
        )


class SyncThruOnlineSensor(SyncThruBinarySensor):
    """Implementation of a sensor that checks whether is turned on/online."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: DataUpdateCoordinator[SyncThru], name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, name)
        self._id_suffix = "_online"

    @property
    def is_on(self):
        """Set the state to whether the printer is online."""
        return self.syncthru.is_online()


class SyncThruProblemSensor(SyncThruBinarySensor):
    """Implementation of a sensor that checks whether the printer works correctly."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, syncthru, name):
        """Initialize the sensor."""
        super().__init__(syncthru, name)
        self._id_suffix = "_problem"

    @property
    def is_on(self):
        """Set the state to whether there is a problem with the printer."""
        return SYNCTHRU_STATE_PROBLEM[self.syncthru.device_status()]
