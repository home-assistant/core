"""TuneBladeEntity base class."""

import logging

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MASTER_ID, NAME
from .coordinator import TuneBladeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class TuneBladeEntity(CoordinatorEntity[TuneBladeDataUpdateCoordinator]):
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
        self.device_id = device_id
        self.device_name = device_name
        self._attr_unique_id = f"{config_entry.entry_id}_{self.device_id}"

        if self.device_id and self.device_id == MASTER_ID:
            _LOGGER.debug("Found MASTER: %s", self.device_id)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, MASTER_ID)},
                name=self.device_name,
                manufacturer=NAME,
                entry_type=DeviceEntryType.SERVICE,
            )

        elif self.device_id and self.device_id != "MASTER":
            _LOGGER.debug("Found device: %s", self.device_id)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.device_id)},
                via_device=(DOMAIN, MASTER_ID),
                name=self.device_name,
                manufacturer=NAME,
            )
