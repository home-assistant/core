"""Coordinator for Cielo integration."""

from __future__ import annotations

from collections.abc import Callable
from copy import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final

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
from homeassistant.helpers.event import async_call_later
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
        self._known_device_ids: set[str] = set()
        self._cancel_delayed_refresh: Callable[[], None] | None = None

    async def _async_update_data(self) -> CieloData:
        """Fetch data from the API."""
        try:
            data = await self.client.get_devices_data()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except (TimeoutError, CieloError, ClientError) as err:
            raise UpdateFailed(err) from err

        new_ids = set(data.parsed.keys()) if data.parsed else set()
        removed_ids = self._known_device_ids - new_ids

        if removed_ids:
            dev_reg = dr.async_get(self.hass)
            for dev_id in removed_ids:
                device = dev_reg.async_get_device(identifiers={(DOMAIN, dev_id)})
                if device:
                    dev_reg.async_update_device(
                        device.id, remove_config_entry_id=self.config_entry.entry_id
                    )

        self._known_device_ids = new_ids
        raw = dict(data.raw or {})
        parsed = dict(data.parsed or {})
        return CieloData(raw=raw, parsed=parsed)

    async def async_apply_action_result(
        self, device_id: str, data: dict[str, Any]
    ) -> None:
        """Apply an optimistic update from an API action response.

        This updates coordinator data immediately (so all entities update together),
        then schedules a refresh to reconcile with the backend once it catches up.
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

        if self._cancel_delayed_refresh is not None:
            self._cancel_delayed_refresh()
            self._cancel_delayed_refresh = None

        async def _refresh_later(_now: datetime) -> None:
            """Schedule a refresh after the backend has had time to update."""
            self._cancel_delayed_refresh = None
            self.hass.async_create_task(self.async_request_refresh())

        self._cancel_delayed_refresh = async_call_later(self.hass, 2.0, _refresh_later)

    async def async_shutdown(self) -> None:
        """Cancel pending callbacks when the coordinator shuts down."""
        if self._cancel_delayed_refresh is not None:
            self._cancel_delayed_refresh()
            self._cancel_delayed_refresh = None


# Define the ConfigEntry type here to avoid circular imports
type CieloHomeConfigEntry = ConfigEntry[CieloDataUpdateCoordinator]
