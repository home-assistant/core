"""An abstract class common to all Imou entities."""

from typing import override

from pyimouapi.ha_device import DeviceStatus, ImouHaDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PARAM_STATE, PARAM_STATUS, imou_device_identifier
from .coordinator import ImouDataUpdateCoordinator


class ImouEntity(CoordinatorEntity[ImouDataUpdateCoordinator]):
    """Base class for all Imou entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        description: EntityDescription,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entity_type = description.key
        self._device_key = imou_device_identifier(device)
        self._attr_unique_id = f"{self._device_key}${description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_key)},
            name=device.channel_name or device.device_name,
            manufacturer=device.manufacturer,
            model=device.model,
            sw_version=device.swversion,
            serial_number=device.device_id,
        )

    @property
    def device(self) -> ImouHaDevice:
        """Return the live device from the coordinator.

        Callers must guard with `available` first; accessing this for a device
        that has left the account raises `KeyError`.
        """
        return self.coordinator.devices_by_key[self._device_key]

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        if (
            not super().available
            or self._device_key not in self.coordinator.devices_by_key
        ):
            return False
        if PARAM_STATUS not in self.device.sensors:
            return False
        return (
            self.device.sensors[PARAM_STATUS][PARAM_STATE] != DeviceStatus.OFFLINE.value
        )
