"""Base entity for the Electra Smart integration."""

from typing import override

from electrasmart.device import ElectraAirConditioner

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, UNAVAILABLE_THRESH_SEC
from .coordinator import ElectraSmartCoordinator


class ElectraEntity(CoordinatorEntity[ElectraSmartCoordinator]):
    """Define a base Electra AC entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ElectraSmartCoordinator, device: ElectraAirConditioner
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.mac)},
            connections={(CONNECTION_NETWORK_MAC, device.mac)},
            name=device.name,
            model=device.model or None,
            manufacturer=device.manufactor or None,
            serial_number=device.serial_number or None,
            sw_version=device.fm_version or None,
            hw_version=device.hw_version or None,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the AC is available.

        The coordinator reports a failed poll as a successful refresh, so its
        availability says nothing about a single AC. Report an AC that has
        stopped sending telemetry as unavailable instead of serving the state
        it last reported.
        """
        return (
            not self._device.is_disconnected(UNAVAILABLE_THRESH_SEC)
            and super().available
        )
