"""Coordinator for Cielo integration."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from aiohttp import ClientError
from cieloconnectapi import CieloClient
from cieloconnectapi.exceptions import AuthenticationError, CieloError
from cieloconnectapi.model import CieloDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, TIMEOUT

REQUEST_REFRESH_DELAY: Final[int] = 2 * 60


@dataclass(slots=True)
class CieloData:
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
            config_entry=entry,
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

        raw = dict(data.raw or {})
        parsed = dict(data.parsed or {})
        return CieloData(raw=raw, parsed=parsed)

    async def async_apply_action_result(
        self, device_id: str, data: dict[str, Any]
    ) -> None:
        """Apply an optimistic update from an API action response.

        This updates the affected device locally in the coordinator state so the
        UI reflects the change immediately without requiring a full backend refresh.

        Performing a coordinator refresh after every action would fetch all devices
        for the account, even when only a single device was updated. This is not
        optimal from an API usage/cost perspective.

        Instead, the coordinator applies the action result locally for the affected
        device and schedules a later refresh to reconcile with the backend state.
        """
        if not self.data or not self.data.parsed or device_id not in self.data.parsed:
            await self.async_request_refresh()
            return

        new_parsed = dict(self.data.parsed)
        dev = copy(new_parsed[device_id])

        try:
            dev.apply_update(data)
        except KeyError, ValueError, TypeError:
            await self.async_request_refresh()
            return

        new_parsed[device_id] = dev
        self.async_set_updated_data(CieloData(raw=self.data.raw, parsed=new_parsed))

        # Request a debounced refresh to reconcile with the backend state.
        await self.async_request_refresh()


# Define the ConfigEntry type here to avoid circular imports
type CieloHomeConfigEntry = ConfigEntry[CieloDataUpdateCoordinator]
