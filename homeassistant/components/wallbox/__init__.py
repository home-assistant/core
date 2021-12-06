"""The Wallbox integration."""
from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any, Dict

import requests
from wallbox import Wallbox

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_DATA_KEY, CONF_MAX_CHARGING_CURRENT_KEY, CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number"]
UPDATE_INTERVAL = 30


class WallboxCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Wallbox Coordinator class."""

    def __init__(self, station: str, wallbox: Wallbox, hass: HomeAssistant) -> None:
        """Initialize."""
        self._station = station
        self._wallbox = wallbox

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    def _authenticate(self) -> None:
        """Authenticate using Wallbox API."""
        try:
            self._wallbox.authenticate()
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == HTTPStatus.FORBIDDEN:
                raise ConfigEntryAuthFailed from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error

    def _validate(self) -> None:
        """Authenticate using Wallbox API."""
        try:
            self._wallbox.authenticate()
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InvalidAuth from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error

    def _get_data(self) -> dict[str, Any]:
        """Get new sensor data for Wallbox component."""
        try:
            self._authenticate()
            data: dict[str, Any] = self._wallbox.getChargerStatus(self._station)
            data[CONF_MAX_CHARGING_CURRENT_KEY] = data[CONF_DATA_KEY][
                CONF_MAX_CHARGING_CURRENT_KEY
            ]

            return data

        except requests.exceptions.HTTPError as wallbox_connection_error:
            raise ConnectionError from wallbox_connection_error

    def _set_charging_current(self, charging_current: float) -> None:
        """Set maximum charging current for Wallbox."""
        try:
            self._authenticate()
            self._wallbox.setMaxChargingCurrent(self._station, charging_current)
        except requests.exceptions.HTTPError as wallbox_connection_error:
            if wallbox_connection_error.response.status_code == 403:
                raise InvalidAuth from wallbox_connection_error
            raise ConnectionError from wallbox_connection_error

    async def async_set_charging_current(self, charging_current: float) -> None:
        """Set maximum charging current for Wallbox."""
        await self.hass.async_add_executor_job(
            self._set_charging_current, charging_current
        )
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Get new sensor data for Wallbox component."""
        data = await self.hass.async_add_executor_job(self._get_data)
        return data

    async def async_validate_input(self) -> None:
        """Get new sensor data for Wallbox component."""
        await self.hass.async_add_executor_job(self._validate)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wallbox from a config entry."""
    wallbox = Wallbox(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    wallbox_coordinator = WallboxCoordinator(
        entry.data[CONF_STATION],
        wallbox,
        hass,
    )

    try:
        await wallbox_coordinator.async_validate_input()

    except InvalidAuth as ex:
        raise ConfigEntryAuthFailed from ex

    await wallbox_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = wallbox_coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
