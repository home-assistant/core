"""Shared polling for FortiOS trackers."""

from datetime import datetime, timedelta
import logging
from typing import override

from fortiosapi import NotLogged
from requests.exceptions import RequestException

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import FortiOSClient, FortiOSDevice
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)
type FortiOSConfigEntry = ConfigEntry[FortiOSCoordinator]


class FortiOSCoordinator(DataUpdateCoordinator[dict[str, FortiOSDevice]]):
    """Poll one client list for all tracker entities."""

    def __init__(
        self, hass: HomeAssistant, entry: FortiOSConfigEntry, client: FortiOSClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.data.get(
                    CONF_SCAN_INTERVAL, UPDATE_INTERVAL.total_seconds()
                )
            ),
        )
        self.client = client
        self.last_seen: dict[str, datetime] = {}
        self.consider_home = entry.data.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )

    @override
    async def _async_update_data(self) -> dict[str, FortiOSDevice]:
        """Read client state in the executor."""
        try:
            devices = await self.hass.async_add_executor_job(self.client.update)
        except NotLogged as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except RequestException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        for mac, device in devices.items():
            if device.online:
                self.last_seen[mac] = dt_util.utcnow()
        return devices
