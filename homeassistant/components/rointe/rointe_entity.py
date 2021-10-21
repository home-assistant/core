"""Rointe devices entity model."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ROINTE_MANUFACTURER
from .coordinator import RointeDataUpdateCoordinator
from .device_manager import RointeDevice, RointeDeviceManager


class RointeHAEntity(CoordinatorEntity):
    """Rointe entity base class."""

    def __init__(
        self, coordinator: RointeDataUpdateCoordinator, name: str, unique_id: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"rointe-{unique_id}"
        self._attr_name = name

    @property
    def device_manager(self) -> RointeDeviceManager:
        """Return the device manager."""
        return self.coordinator.device_manager


class RointeRadiatorEntity(RointeHAEntity):
    """Base class for entities that support a Radiator device (climate and sensors)."""

    def __init__(
        self,
        coordinator: RointeDataUpdateCoordinator,
        radiator: RointeDevice,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, name, unique_id)
        self._radiator = radiator

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""

        if self._radiator.rointe_product:
            product_name = self._radiator.rointe_product.product_name
        else:
            product_name = (
                f"{self._radiator.type.capitalize()} {self._radiator.product_version.capitalize()}",
            )

        return DeviceInfo(
            identifiers={(DOMAIN, self._radiator.id)},
            manufacturer=ROINTE_MANUFACTURER,
            name=self._radiator.name,
            model=product_name,
            sw_version=self._radiator.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._radiator and self._radiator.hass_available
