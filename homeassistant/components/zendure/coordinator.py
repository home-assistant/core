"""Data update coordinator for Zendure devices."""

from typing import override

from zendure import DeviceSnapshot, ZendureClient, ZendureConnectionError, ZendureError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type ZendureConfigEntry = ConfigEntry[ZendureDataUpdateCoordinator]


class ZendureDataUpdateCoordinator(DataUpdateCoordinator[DeviceSnapshot]):
    """Poll one Zendure device over the local network."""

    config_entry: ZendureConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ZendureConfigEntry,
        client: ZendureClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.unique_id}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> DeviceSnapshot:
        """Fetch the latest snapshot from the device."""
        try:
            return await self.client.async_refresh()
        except ZendureConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except ZendureError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(err)},
            ) from err
