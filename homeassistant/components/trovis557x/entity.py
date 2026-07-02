"""Base entity for Trovis 557x.

Each heating circuit and the hot water tank are their own (sub-)device, linked to
the controller via ``via_device``; everything else belongs to the controller.
"""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TrovisCoordinator


def _sub_device(component: str) -> tuple[str, str] | None:
    """(sub-device id, name) for a component, or None for the controller."""
    if component.startswith("heating_circuit_"):
        number = component.rsplit("_", 1)[1]
        return f"circuit_{number}", f"Heating circuit {number}"
    if component == "hot_water":
        return "hot_water", "Hot water"
    return None


class TrovisEntity(CoordinatorEntity[TrovisCoordinator]):
    """Common identity + device-info for every Trovis entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TrovisCoordinator, key: str, component: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._component = component
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        info = coordinator.device.info
        sub = _sub_device(component)
        if sub is None:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry.entry_id)},
                manufacturer=info.manufacturer,
                model=info.model,
                name=info.model,
                sw_version=info.firmware_version,
                hw_version=info.hardware_version,
                serial_number=info.serial_number,
            )
        else:
            sub_id, sub_name = sub
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{entry.entry_id}_{sub_id}")},
                manufacturer=info.manufacturer,
                name=sub_name,
                via_device=(DOMAIN, entry.entry_id),
            )

    @property
    def _subsystem(self) -> object:
        """The library sub-system object this entity reads from."""
        return getattr(self.coordinator.device, self._component)
