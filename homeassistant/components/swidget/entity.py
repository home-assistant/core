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
        self.device = device
        self._attr_unique_id = device.id
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac_address)},
            identifiers={(DOMAIN, str(device.id))},
            manufacturer="Swidget",
            model=device.model,
            name=device.friendly_name,
            sw_version=device.version,
        )
