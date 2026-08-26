"""DataUpdateCoordinator for Hot Spring."""

from typing import override

from hotspring import (
    HotSpring,
    HotSpringConnectionError,
    HotSpringError,
    LightZone,
    Spa,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
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
        self.light_zones: dict[int, LightZone] = {}
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    @callback
    @override
    def async_set_updated_data(self, data: Spa) -> None:
        """Manually update data, notify listeners and reset refresh interval."""
        self.light_zones = {zone.zone_id: zone for zone in data.light_zones}
        super().async_set_updated_data(data)

    @override
    async def _async_update_data(self) -> Spa:
        """Fetch data from Hot Spring."""
        try:
            spa = await self.hotspring.update()
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

        if (
            not spa.info.mac_address
            or spa.info.mac_address != self.config_entry.unique_id
        ):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            )

        self.light_zones = {zone.zone_id: zone for zone in spa.light_zones}
        return spa
