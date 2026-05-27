"""An abstract class common to all Imou entities."""

from pyimouapi.ha_device import DeviceStatus, ImouHaDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PARAM_STATE, PARAM_STATUS, imou_device_identifier
from .coordinator import ImouDataUpdateCoordinator


class ImouEntity(CoordinatorEntity[ImouDataUpdateCoordinator]):
    """Base class for all Imou entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        entity_type: str,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou entity."""
        super().__init__(coordinator)
        self._entity_type = entity_type
        self._device = device
        device_key = imou_device_identifier(device)
        self._attr_unique_id = f"{device_key}${entity_type}"
        self._attr_translation_key = entity_type
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_key)},
            name=device.channel_name or device.device_name,
            manufacturer=device.manufacturer,
            model=device.model,
            sw_version=device.swversion,
            serial_number=device.device_id,
        )

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        if not super().available:
            return False
        if PARAM_STATUS not in self._device.sensors:
            return False
        return (
            self._device.sensors[PARAM_STATUS][PARAM_STATE]
            != DeviceStatus.OFFLINE.value
        )
