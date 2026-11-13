"""DataUpdateCoordinator for Hot Spring."""

from typing import override

from hotspring import (
    HotSpring,
    HotSpringConnectionError,
    HotSpringConnectionTimeoutError,
    HotSpringError,
    Spa,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type HotSpringConfigEntry = ConfigEntry[HotSpringDataUpdateCoordinator]


class HotSpringDataUpdateCoordinator(DataUpdateCoordinator[Spa]):
    """Class to manage fetching Hot Spring data from a single endpoint."""

    config_entry: HotSpringConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: HotSpringConfigEntry) -> None:
        """Initialize global Hot Spring data updater."""
        self.hotspring = HotSpring(
            config_entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> Spa:
        """Fetch data from Hot Spring."""
        try:
            spa = await self.hotspring.update()
        except HotSpringConnectionTimeoutError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout",
            ) from error
        except HotSpringConnectionError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from error
        except HotSpringError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            ) from error

        if spa.info.mac_address != self.config_entry.unique_id:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="wrong_device",
                translation_placeholders={
                    "found": spa.info.mac_address or "unknown",
                    "expected": str(self.config_entry.unique_id),
                },
            )

        return spa
