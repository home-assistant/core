"""Shared entity base — device_info and the coordinator plumbing."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import SofarDataUpdateCoordinator


def build_device_info(coordinator: SofarDataUpdateCoordinator) -> DeviceInfo:
    """The one physical inverter every entity on this config entry belongs to."""
    device = coordinator.device
    serial = device.serial_number
    assert (
        serial is not None
    )  # set by async_setup(), which the coordinator's first refresh requires
    assert (
        coordinator.config_entry is not None
    )  # always constructed with one; see coordinator.py
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        name=coordinator.config_entry.title,
        manufacturer=ATTR_MANUFACTURER,
        model=device.model or None,
        serial_number=serial,
    )


class SofarEntity(CoordinatorEntity[SofarDataUpdateCoordinator]):
    """Base for every Sofar entity — one physical inverter per config entry.

    ``component`` is the attribute name on ``coordinator.device`` this entity
    reads or writes (e.g. ``'grid'``, ``'feed_in'``) — used by ``available``
    below so only the entities on a component that actually failed this poll
    go unavailable, not all of them.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SofarDataUpdateCoordinator,
        unique_id_suffix: str,
        component: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        serial = coordinator.device.serial_number
        assert (
            serial is not None
        )  # set by async_setup(), which the coordinator's first refresh requires
        self._component = component
        self._attr_unique_id = f"{serial}_{unique_id_suffix}"
        self._attr_device_info = build_device_info(coordinator)

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
            return False  # the link is down; nothing refreshed at all
        report = self.coordinator.data
        return report is None or self._component not in report.failed
