"""Shared BUSY Bar entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BusyCoordinator


class BusyEntity(CoordinatorEntity[BusyCoordinator]):
    """A reading belonging to one bar."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BusyCoordinator, key: str) -> None:
        """Attach a stable identity and device metadata.

        Bind the shared coordinator and the state required by this instance.
        """
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry is not None
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        data = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
            name=entry.title,
            manufacturer="BUSY",
            model="BUSY Bar",
            serial_number=data.serial,
            hw_version=data.hardware,
            sw_version=data.firmware,
            configuration_url=coordinator.client.base_url,
        )
