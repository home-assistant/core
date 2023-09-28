"""Freedompro data update coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyfreedompro import get_list, get_states

from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FreedomproDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching Freedompro data API."""

    def __init__(self, hass, api_key):
        """Initialize."""
        self._hass = hass
        self._api_key = api_key
        self._devices: list[dict[str, Any]] | None = None

        update_interval = timedelta(minutes=1)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self):
        if self._devices is None:
            result = await get_list(
                aiohttp_client.async_get_clientsession(self._hass), self._api_key
            )
            if result["state"]:
                self._devices = result["devices"]
            else:
                raise UpdateFailed()

        result = await get_states(
            aiohttp_client.async_get_clientsession(self._hass), self._api_key
        )

        for device in self._devices:
            dev = next(
                (dev for dev in result if dev["uid"] == device["uid"]),
                None,
            )
            if dev is not None and "state" in dev:
                device["state"] = dev["state"]
        return self._devices
