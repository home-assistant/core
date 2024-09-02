"""Base entity for Iskra devices."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import IskraDataUpdateCoordinator


class IskraEntity(CoordinatorEntity):
    """Representation a base Iskra device."""

    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(self, coordinator: IskraDataUpdateCoordinator) -> None:
        """Initialize the Iskra device."""
        super().__init__(coordinator)
        device = coordinator.device
        self._state = None
        self._serial = device.serial
        self._model = device.model
        self._fw_version = device.fw_version
        self._device_name = f"{self._serial}"
        self._device = device
        self._is_gateway = self._device.is_gateway
        self._gateway = device.parent_device
        self._device_id = self._serial

    @property
    def device_id(self) -> str:
        """Return the device id of the Iskra device."""
        return self._device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info of the Iskra device."""
        # If device has gateway add via_device property
        if self._gateway:
            return DeviceInfo(
                connections={("IP", self._device_id)},
                identifiers={(DOMAIN, self._device_id)},
                manufacturer=MANUFACTURER,
                model=self._model,
                name=self._device_name,
                sw_version=self._fw_version,
                serial_number=self._serial,
                via_device=(DOMAIN, self._gateway.serial),
            )

        return DeviceInfo(
            connections={("IP", self._device_id)},
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=MANUFACTURER,
            model=self._model,
            name=self._device_name,
            sw_version=self._fw_version,
            serial_number=self._serial,
        )
