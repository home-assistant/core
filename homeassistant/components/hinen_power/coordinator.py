"""DataUpdateCoordinator for the Hinen Power integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, override

from hinen_open_api.exceptions import HinenBackendError, UnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .auth_config import AsyncConfigEntryAuth
from .const import (
    ATTR_ALERT_STATUS,
    ATTR_DEVICE_NAME,
    ATTR_SERIAL_NUMBER,
    ATTR_STATUS,
    DOMAIN,
    LOGGER,
    PROPERTIES,
)

type HinenPowerConfigEntry = ConfigEntry[HinenPowerRuntimeData]


class HinenDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """A Hinen Data Update Coordinator."""

    config_entry: HinenPowerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HinenPowerConfigEntry,
        auth: AsyncConfigEntryAuth,
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

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Hinen."""
        hinen_open = await self._auth.get_resource()
        res = {}
        try:
            device_infos = [
                device_info async for device_info in hinen_open.get_device_infos()
            ]
            device_ids = [str(device_info.id) for device_info in device_infos]
            async for device_detail in hinen_open.get_device_details(device_ids):
                res[device_detail.id] = {
                    ATTR_SERIAL_NUMBER: device_detail.serial_number,
                    ATTR_DEVICE_NAME: device_detail.device_name,
                    ATTR_STATUS: device_detail.status,
                    ATTR_ALERT_STATUS: device_detail.alert_status,
                    **{
                        key: next(
                            (
                                prop.value
                                for prop in device_detail.properties
                                if prop.identifier == identifier
                            ),
                            None,
                        )
                        for key, identifier in PROPERTIES.items()
                    },
                }
        except UnauthorizedError as err:
            raise ConfigEntryAuthFailed from err
        except HinenBackendError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err
        return res


@dataclass
class HinenPowerRuntimeData:
    """Hinen power runtime data."""

    coordinator: HinenDataUpdateCoordinator
    auth: AsyncConfigEntryAuth
