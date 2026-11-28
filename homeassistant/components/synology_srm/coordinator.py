"""Fetch devices from a Synology SRM router."""

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any, override

from requests.exceptions import RequestException
from synology_srm import Client
from synology_srm.http import SynologyApiError, SynologyException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type SynologySrmConfigEntry = ConfigEntry[SynologySrmCoordinator]


def create_client(data: Mapping[str, Any]) -> Client:
    """Create a router client."""
    client = Client(
        host=data[CONF_HOST],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        https=data[CONF_SSL],
    )
    if not data[CONF_VERIFY_SSL]:
        client.http.disable_https_verify()
    return client


class SynologySrmCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinate device updates."""

    config_entry: SynologySrmConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SynologySrmConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.client = create_client(entry.data)

    @override
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch both online and offline devices."""
        try:
            devices = await self.hass.async_add_executor_job(
                self.client.core.get_network_nsm_device
            )
        except SynologyApiError as err:
            if err.code in (400, 401, 402, 403, 404):
                raise ConfigEntryAuthFailed from err
            raise UpdateFailed("Error fetching Synology SRM devices") from err
        except (SynologyException, RequestException) as err:
            raise UpdateFailed("Error fetching Synology SRM devices") from err
        return {format_mac(device["mac"]): device for device in devices}
