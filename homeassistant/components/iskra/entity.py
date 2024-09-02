"""Base entity for Iskra devices."""

from pyiskra.devices import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER


class IskraEntity(Entity):
    """Representation a base Iskra device."""

    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(self, device: Device, config_entry: ConfigEntry) -> None:
        """Initialize the Iskra device."""
        self._state = None
        self._is_available = True
        self._serial = device.serial
        self._model = device.model
        self._fw_version = device.fw_version
        self._device_name = f"{self._serial}"
        self._remove_unavailability_tracker = None
        self._device = device
        self._is_gateway = self._device.is_gateway

        self._gateway = device.parent_device
        self._device_id = self._serial

    @property
    def device_id(self):
        """Return the device id of the Iskra device."""
        return self._device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info of the Iskra device."""
        if self._is_gateway or self._gateway is None:
            device_info = DeviceInfo(
                connections={("IP", self._device_id)},
                identifiers={(DOMAIN, self._device_id)},
                manufacturer=MANUFACTURER,
                model=self._model,
                name=self._device_name,
                sw_version=self._fw_version,
                serial_number=self._serial,
            )
        else:
            device_info = DeviceInfo(
                connections={("IP", self._device_id)},
                identifiers={(DOMAIN, self._device_id)},
                manufacturer=MANUFACTURER,
                model=self._model,
                name=self._device_name,
                sw_version=self._fw_version,
                serial_number=self._serial,
                via_device=(DOMAIN, self._gateway.serial),
            )

        return device_info
