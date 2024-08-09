"""Common code for Swidget."""

from __future__ import annotations

from swidget.swidgetdevice import SwidgetDevice

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwidgetDataUpdateCoordinator


class CoordinatedSwidgetEntity(CoordinatorEntity[SwidgetDataUpdateCoordinator]):
    """Common base class for all coordinated entities."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, device: SwidgetDevice, coordinator: SwidgetDataUpdateCoordinator
    ) -> None:
        """Initialize the Swidget device."""
        super().__init__(coordinator)
        self.device: SwidgetDevice = device
        self._attr_unique_id = self.device.id

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac_address)},
            identifiers={(DOMAIN, str(self.device.id))},
            manufacturer="Swidget",
            model=self.device.model,
            name=self.device.friendly_name,
            sw_version=self.device.version,
        )
