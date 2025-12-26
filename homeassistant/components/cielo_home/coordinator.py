"""Coordinator for Cielo integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final, NamedTuple

from aiohttp import ClientError
from cieloconnectapi import CieloClient
from cieloconnectapi.exceptions import AuthenticationError, CieloError
from cieloconnectapi.model import CieloDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, TIMEOUT

REQUEST_REFRESH_DELAY: Final[int] = 2 * 60


class CieloData(NamedTuple):
    """Data structure for the coordinator."""

    raw: dict[str, Any]
    parsed: dict[str, CieloDevice]


class CieloDataUpdateCoordinator(DataUpdateCoordinator[CieloData]):
    """Cielo Data Update Coordinator."""

    config_entry: CieloHomeConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CieloHomeConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = CieloClient(
            api_key=entry.data[CONF_API_KEY],
            timeout=TIMEOUT,
            token=entry.data[CONF_TOKEN],
            session=async_get_clientsession(hass),
        )

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> CieloData:
        """Fetch data from the API."""
        try:
            data = await self.client.get_devices_data()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except (TimeoutError, CieloError, ClientError) as err:
            raise UpdateFailed(err) from err

        # Handle removed devices by removing this config entry from them
        if self.data and self.data.parsed:
            old_ids = set(self.data.parsed.keys())
            new_ids = set(data.parsed.keys()) if data.parsed else set()
            removed_ids = old_ids - new_ids

            if removed_ids:
                dev_reg = dr.async_get(self.hass)
                for dev_id in removed_ids:
                    device = dev_reg.async_get_device(identifiers={(DOMAIN, dev_id)})
                    if device:
                        dev_reg.async_update_device(
                            device.id, remove_config_entry_id=self.config_entry.entry_id
                        )

        parsed = dict(data.parsed or {})
        return CieloData(raw=data.raw, parsed=parsed)


# Define the ConfigEntry type here to avoid circular imports
type CieloHomeConfigEntry = ConfigEntry[CieloDataUpdateCoordinator]
