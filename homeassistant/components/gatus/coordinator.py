"""DataUpdateCoordinator for the Gatus integration."""

from datetime import timedelta
import logging
from typing import override

from gatus_api import EndpointStatus, GatusClient, GatusClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type GatusConfigEntry = ConfigEntry[GatusDataUpdateCoordinator]


class GatusDataUpdateCoordinator(DataUpdateCoordinator[dict[str, EndpointStatus]]):
    """Class to manage fetching Gatus data from the API via third-party library."""

    def __init__(self, hass: HomeAssistant, entry: GatusConfigEntry, url: str) -> None:
        """Initialize the coordinator."""
        self.url = url.rstrip("/")
        self.client = GatusClient(url=self.url, session=async_get_clientsession(hass))
        self._entry_id = entry.entry_id
        device_registry = dr.async_get(hass)
        self._known_endpoint_keys = {
            identifier[1].removeprefix(f"{entry.entry_id}_")
            for device in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            )
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
            and identifier[1].startswith(f"{entry.entry_id}_")
        }

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    @override
    async def _async_update_data(self) -> dict[str, EndpointStatus]:
        """Fetch endpoint statuses from the Gatus API."""
        try:
            raw_endpoints = await self.client.get_endpoints_statuses()
        except GatusClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from err

        current_keys = {ep.key for ep in raw_endpoints}
        stale_keys = self._known_endpoint_keys - current_keys
        if stale_keys:
            device_registry = dr.async_get(self.hass)
            for key in stale_keys:
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, f"{self._entry_id}_{key}")}
                )
                if device is not None:
                    device_registry.async_update_device(
                        device.id,
                        remove_config_entry_id=self._entry_id,
                    )
        self._known_endpoint_keys = current_keys

        return {ep.key: ep for ep in raw_endpoints}
