"""Base entity for KEBA P40."""

from keba_kecontact_p40 import Wallbox, WallboxState

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import KebaP40DataUpdateCoordinator


class KebaP40Entity(CoordinatorEntity[KebaP40DataUpdateCoordinator]):
    """Base class for all KEBA P40 entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KebaP40DataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial}_{description.key}"
        wallbox = coordinator.data.wallbox
        data = coordinator.config_entry.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial)},
            manufacturer=MANUFACTURER,
            name=wallbox.alias or wallbox.model,
            model=wallbox.model,
            sw_version=wallbox.firmware_version,
            serial_number=coordinator.serial,
            configuration_url=f"https://{data[CONF_HOST]}:{data[CONF_PORT]}",
        )

    @property
    def _wallbox(self) -> Wallbox:
        """Return the current wallbox data."""
        return self.coordinator.data.wallbox

    @property
    def available(self) -> bool:
        """Return True unless polling failed or the wallbox is offline."""
        return super().available and self._wallbox.state is not WallboxState.OFFLINE
