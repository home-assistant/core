"""Base Entity for Sonarr."""
from __future__ import annotations

from sonarr import Sonarr

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class SonarrEntity(Entity):
    """Defines a base Sonarr entity."""

    def __init__(
        self,
        *,
        sonarr: Sonarr,
        entry_id: str,
        device_id: str,
    ) -> None:
        """Initialize the Sonarr entity."""
        self._entry_id = entry_id
        self._device_id = device_id
        self.sonarr = sonarr

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about the application."""
        if self._device_id is None:
            return None

        configuration_url = "https://" if self.sonarr.tls else "http://"
        configuration_url += f"{self.sonarr.host}:{self.sonarr.port}"
        configuration_url += self.sonarr.base_path.replace("/api", "")

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name="Activity Sensor",
            manufacturer="Sonarr",
            sw_version=self.sonarr.app.info.version,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=configuration_url,
        )
