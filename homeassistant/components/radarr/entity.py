"""Base Entity for Radarr."""
from __future__ import annotations

from aiopyarr import RadarrClient

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class RadarrEntity(Entity):
    """Defines a base Radarr entity."""

    def __init__(
        self,
        *,
        radarr: RadarrClient,
        entry_id: str,
        device_id: str,
    ) -> None:
        """Initialize the Radarr entity."""
        self._entry_id = entry_id
        self._device_id = device_id
        self.radarr = radarr

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about the application."""
        if self._device_id is None:
            return None

        # configuration_url = "https://" if self.radarr.tls else "http://"
        # configuration_url += f"{self.radarr.host}:{self.radarr.port}"
        # configuration_url += self.radarr.base_path.replace("/api", "")
        #TODO fix _host
        return DeviceInfo(
            configuration_url=self.radarr._host.base_url,
            entry_type="service",
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Radarr",
            name="Activity Sensor",
            # sw_version=self.radarr.app.info.version,
        )
