"""TuneBladeEntity base class."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import TuneBladeDataUpdateCoordinator


class TuneBladeEntity(CoordinatorEntity):
    """Base entity for TuneBlade devices, including master hub."""

    def __init__(
        self,
        coordinator: TuneBladeDataUpdateCoordinator,
        config_entry,
        device_id: str | None = None,
        device_name: str | None = None,
    ) -> None:
        """Initialize entity with coordinator, config entry, and optional device info."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.device_id = device_id or "master"
        self.device_name = device_name or "Master"

        self._attr_unique_id = f"{config_entry.entry_id}_{self.device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name=f"{self.device_name} {NAME}",
            manufacturer=NAME,
        )
