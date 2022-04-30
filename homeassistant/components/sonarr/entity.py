"""Base Entity for Sonarr."""
from __future__ import annotations

from aiopyarr import SystemStatus
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.sonarr_client import SonarrClient

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class SonarrEntity(Entity):
    """Defines a base Sonarr entity."""

    def __init__(
        self,
        *,
        sonarr: SonarrClient,
        host_config: PyArrHostConfiguration,
        system_status: SystemStatus,
        entry_id: str,
        device_id: str,
    ) -> None:
        """Initialize the Sonarr entity."""
        self._entry_id = entry_id
        self._device_id = device_id
        self.sonarr = sonarr
        self.host_config = host_config
        self.system_status = system_status

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about the application."""
        if self._device_id is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name="Activity Sensor",
            manufacturer="Sonarr",
            sw_version=self.system_status.version,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=self.host_config.base_url,
        )
