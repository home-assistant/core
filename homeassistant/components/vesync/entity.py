"""Common entity for VeSync Component."""

from typing import Any

from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, ToggleEntity

from .const import DOMAIN


class VeSyncBaseEntity(Entity):
    """Base class for VeSync Entity Representations."""

    _attr_has_entity_name = True

    def __init__(self, device: VeSyncBaseDevice) -> None:
        """Initialize the VeSync device."""
        self.device = device
        self._attr_unique_id = self.base_unique_id

    @property
    def base_unique_id(self):
        """Return the ID of this device."""
        # The unique_id property may be overridden in subclasses, such as in
        # sensors. Maintaining base_unique_id allows us to group related
        # entities under a single device.
        if isinstance(self.device.sub_device_no, int):
            return f"{self.device.cid}{self.device.sub_device_no!s}"
        return self.device.cid

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.device.connection_status == "online"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.base_unique_id)},
            name=self.device.device_name,
            model=self.device.device_type,
            manufacturer="VeSync",
            sw_version=self.device.current_firm_version,
        )

    def update(self) -> None:
        """Update vesync device."""
        self.device.update()


class VeSyncDevice(VeSyncBaseEntity, ToggleEntity):
    """Base class for VeSync Device Representations."""

    @property
    def details(self):
        """Provide access to the device details dictionary."""
        return self.device.details

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.device.device_status == "on"

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self.device.turn_off()
