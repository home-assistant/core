"""Paperless-ngx base entity."""

from __future__ import annotations

from pypaperless.exceptions import BadJsonResponseError

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import PaperlessConfigEntry, PaperlessData
from .const import DOMAIN, LOGGER


class PaperlessEntity(Entity):
    """Defines a base Paperless-ngx entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        data: PaperlessData,
        entry: PaperlessConfigEntry,
    ) -> None:
        """Initialize the Paperless-ngx entity."""
        self.client = data.client
        self.inbox_tags = data.inbox_tags
        self.entry = entry

    async def async_update(self) -> None:
        """Update Paperless-ngx entity."""
        if not self.enabled:
            return

        try:
            await self._paperless_update()
            self._attr_available = True
        except BadJsonResponseError as err:
            response = err.args[0]
            status_code = response.status
            if status_code == 403 and self._attr_available:
                self._attr_available = False
                LOGGER.debug(
                    "Paperless-ngx API returned 403 Forbidden. "
                    "Check if the access token is valid and the user has the required permissions",
                )
        except Exception:  # noqa: BLE001
            if self._attr_available:
                LOGGER.debug(
                    "An error occurred while updating the Paperless-ngx sensor",
                    exc_info=True,
                )
            self._attr_available = False

    async def _paperless_update(self) -> None:
        """Update Paperless-ngx entity."""
        raise NotImplementedError

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Paperless-ngx instance."""

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    self.entry.entry_id,
                )
            },
            manufacturer="Paperless-ngx",
            name="Paperless-ngx",
            sw_version=self.client.host_version,
            configuration_url=self.client.base_url,
        )
