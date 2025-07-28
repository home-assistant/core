"""DataUpdateCoordinator for the YouTube integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID, ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .auth_config import AsyncConfigEntryAuth
from .const import (
    ATTR_ALERT_STATUS,
    ATTR_DEVICE_NAME,
    ATTR_STATUS,
    CONF_DEVICES,
    DOMAIN,
    LOGGER,
)
from .hinen_exception import HinenBackendError, UnauthorizedError


class HinenDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """A Hinen Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, auth: AsyncConfigEntryAuth
    ) -> None:
        """Initialize the Hinen data coordinator."""
        self._auth = auth
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        hinen_open = await self._auth.get_resource()
        res = {}
        device_ids = self.config_entry.options[CONF_DEVICES]
        try:
            async for device_detail in hinen_open.get_device_details(device_ids):
                res[device_detail.id] = {
                    ATTR_ID: device_detail.id,
                    ATTR_SERIAL_NUMBER: device_detail.serial_number,
                    ATTR_DEVICE_NAME: device_detail.device_name,
                    ATTR_STATUS: device_detail.status,
                    ATTR_ALERT_STATUS: device_detail.alert_status,
                }
        except UnauthorizedError as err:
            raise ConfigEntryAuthFailed from err
        except HinenBackendError as err:
            raise UpdateFailed("Couldn't connect to Hinen") from err
        return res
