"""Component to embed Aqualink devices."""

from __future__ import annotations

from iaqualink.device import AqualinkDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AqualinkDataUpdateCoordinator


class AqualinkEntity[AqualinkDeviceT: AqualinkDevice](
    CoordinatorEntity[AqualinkDataUpdateCoordinator]
):
    """Abstract class for all Aqualink platforms.

    Entity availability and periodic refreshes are driven by the per-system
    DataUpdateCoordinator. State changes initiated through the iaqualink
    library are propagated back to Home Assistant through the coordinator-aware
    entity update flow.
    """

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: AqualinkDataUpdateCoordinator, dev: AqualinkDeviceT
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.dev = dev
        self._attr_unique_id = f"{dev.system.serial}_{dev.name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            via_device=(DOMAIN, dev.system.serial),
            manufacturer=dev.manufacturer,
            model=dev.model,
            name=dev.label,
        )

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from the device."""
        return self.dev.system.online in [False, None]
