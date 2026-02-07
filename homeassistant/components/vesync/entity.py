"""Common entity for VeSync Component."""

import logging
from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VeSyncDataCoordinator

_LOGGER = logging.getLogger(__name__)


class VeSyncBaseEntity[T: VeSyncBaseDevice](CoordinatorEntity[VeSyncDataCoordinator]):
    """Base class for VeSync Entity Representations."""

    _attr_has_entity_name = True
    _unavailable_logged: bool = False

    def __init__(self, device: T, coordinator: VeSyncDataCoordinator) -> None:
        """Initialize the VeSync device."""
        super().__init__(coordinator)
        self.device = device
        self._attr_unique_id = self.base_unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.base_unique_id)},
            name=self.device.device_name,
            model=self.device.device_type,
            manufacturer="VeSync",
            sw_version=self.device.current_firm_version,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        super()._handle_coordinator_update()
        if not self.available and not self._unavailable_logged:
            _LOGGER.info("The %s device is unavailable", self.device.device_name)
            self._unavailable_logged = True
        elif self.available and self._unavailable_logged:
            _LOGGER.info("The %s device is back online", self.device.device_name)
            self._unavailable_logged = False

    @property
    def base_unique_id(self) -> str:
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
        return super().available and self.device.state.connection_status == "online"
