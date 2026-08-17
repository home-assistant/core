"""Shared entity base — device_info and the coordinator plumbing."""

from typing import TYPE_CHECKING, override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import SofarDataUpdateCoordinator


class SofarEntity(CoordinatorEntity[SofarDataUpdateCoordinator]):
    """Base for every Sofar entity — one physical inverter per config entry."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SofarDataUpdateCoordinator,
        unique_id_suffix: str,
        component: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device = coordinator.device
        serial = device.serial_number
        if TYPE_CHECKING:
            assert serial is not None
            assert coordinator.config_entry is not None
        self._component = component
        self._attr_unique_id = f"{serial}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=coordinator.config_entry.title,
            manufacturer=ATTR_MANUFACTURER,
            model=device.model or None,
            serial_number=serial,
        )

    @property
    def _link_available(self) -> bool:
        """Whether the coordinator's link itself is up, ignoring this entity's own component.

        Exposed separately from ``available`` so a subclass can hold itself
        available through a per-component failure (e.g. a total_increasing
        counter) without also masking a dead link.
        """
        return super().available

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not self._link_available:
            return False
        report = self.coordinator.data
        return report is None or self._component not in report.failed
