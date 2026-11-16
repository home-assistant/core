"""Base entity for the Spin EV Charger integration."""

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, MANUFACTURER, MODEL
from .coordinator import SpinEvCoordinator


class SpinEvEntity(CoordinatorEntity[SpinEvCoordinator]):
    """An entity backed by a charger status snapshot."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SpinEvCoordinator, description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description

        address = coordinator.address
        serial = coordinator.config_entry.data[CONF_SERIAL]

        self._attr_unique_id = f"{address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, address)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=coordinator.config_entry.title,
            serial_number=serial,
            sw_version=coordinator.data.firmware_version,
        )
