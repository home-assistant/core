"""DataUpdateCoordinator for the co2signal integration."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any, cast

import CO2Signal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_COUNTRY_CODE, DOMAIN
from .exceptions import APIRatelimitExceeded, CO2Error, InvalidAuth, UnknownError
from .models import CO2SignalResponse

_LOGGER = logging.getLogger(__name__)


class CO2SignalCoordinator(DataUpdateCoordinator[CO2SignalResponse]):
    """Data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=15)
        )
        self._entry = entry

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    async def _async_update_data(self) -> CO2SignalResponse:
        """Fetch the latest data from the source."""
        try:
            data = await self.hass.async_add_executor_job(
                get_data, self.hass, self._entry.data
            )
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except CO2Error as err:
            raise UpdateFailed(str(err)) from err

        return data


def get_data(hass: HomeAssistant, config: Mapping[str, Any]) -> CO2SignalResponse:
    """Get data from the API."""
    if CONF_COUNTRY_CODE in config:
        latitude = None
        longitude = None
    else:
        latitude = config.get(CONF_LATITUDE, hass.config.latitude)
        longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    try:
        data = CO2Signal.get_latest(
            config[CONF_API_KEY],
            config.get(CONF_COUNTRY_CODE),
            latitude,
            longitude,
            wait=False,
        )

    except ValueError as err:
        err_str = str(err)

        if "Invalid authentication credentials" in err_str:
            raise InvalidAuth from err
        if "API rate limit exceeded." in err_str:
            raise APIRatelimitExceeded from err

        _LOGGER.exception("Unexpected exception")
        raise UnknownError from err

    if "error" in data:
        raise UnknownError(data["error"])

    if data.get("status") != "ok":
        _LOGGER.exception("Unexpected response: %s", data)
        raise UnknownError

    return cast(CO2SignalResponse, data)
