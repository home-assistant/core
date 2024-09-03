"""Base entity for Iskra devices."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import IskraDataUpdateCoordinator


class IskraEntity(CoordinatorEntity[IskraDataUpdateCoordinator]):
    """Representation a base Iskra device."""

    _attr_should_poll = True
    _attr_has_entity_name = True

    def __init__(self, coordinator: IskraDataUpdateCoordinator) -> None:
        """Initialize the Iskra device."""
        super().__init__(coordinator)
        self._device = coordinator.device

        self._serial = self._device.serial
        self._model = self._device.model
        self._fw_version = self._device.fw_version
        self._device_name = f"{self._serial}"
        self._is_gateway = self._device.is_gateway
        self._gateway = self._device.parent_device
        self._device_id = self._serial

        if self._gateway is not None:
            self._attr_device_info = DeviceInfo(
                connections={("IP", self._device_id)},
                identifiers={(DOMAIN, self._device_id)},
                manufacturer=MANUFACTURER,
                model=self._model,
                name=self._device_name,
                sw_version=self._fw_version,
                serial_number=self._serial,
                via_device=(DOMAIN, self._gateway.serial),
            )
        else:
            self._attr_device_info = DeviceInfo(
                connections={("IP", self._device_id)},
                identifiers={(DOMAIN, self._device_id)},
                manufacturer=MANUFACTURER,
                model=self._model,
                name=self._device_name,
                sw_version=self._fw_version,
                serial_number=self._serial,
            )
