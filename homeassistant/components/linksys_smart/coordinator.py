"""Linksys Smart Wi-Fi data update coordinator."""

from datetime import timedelta
import logging
from typing import Any, override

from jnap import JNAPClient, JNAPDevice, JNAPError, JNAPUnauthorizedError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type LinksysConfigEntry = ConfigEntry[LinksysDataUpdateCoordinator]


class LinksysDataUpdateCoordinator(DataUpdateCoordinator[dict[str, JNAPDevice]]):
    """Coordinator to fetch the connected device list from the Linksys router."""

    config_entry: LinksysConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LinksysConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=30),
        )
        kwargs: dict[str, Any] = {}
        if username := entry.data.get(CONF_USERNAME):
            kwargs["username"] = username
        self.client = JNAPClient(
            entry.data[CONF_HOST],
            async_get_clientsession(hass),
            entry.data[CONF_PASSWORD],
            **kwargs,
        )

    @override
    async def _async_update_data(self) -> dict[str, JNAPDevice]:
        """Fetch the current device list from the router."""
        try:
            response = await self.client.get_devices()
        except JNAPUnauthorizedError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except JNAPError as err:
            raise UpdateFailed(str(err)) from err
        return {device.mac: device for device in response.devices}
