"""The CO2 Signal integration."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any, TypedDict, cast

import CO2Signal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_COUNTRY_CODE, DOMAIN

PLATFORMS = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


class CO2SignalData(TypedDict):
    """Data field."""

    carbonIntensity: float
    fossilFuelPercentage: float


class CO2SignalUnit(TypedDict):
    """Unit field."""

    carbonIntensity: str


class CO2SignalResponse(TypedDict):
    """API response."""

    status: str
    countryCode: str
    data: CO2SignalData
    units: CO2SignalUnit


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CO2 Signal from a config entry."""
    coordinator = CO2SignalCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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


class CO2Error(HomeAssistantError):
    """Base error."""


class InvalidAuth(CO2Error):
    """Raised when invalid authentication credentials are provided."""


class APIRatelimitExceeded(CO2Error):
    """Raised when the API rate limit is exceeded."""


class UnknownError(CO2Error):
    """Raised when an unknown error occurs."""


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

    else:
        if "error" in data:
            raise UnknownError(data["error"])

        if data.get("status") != "ok":
            _LOGGER.exception("Unexpected response: %s", data)
            raise UnknownError

    return cast(CO2SignalResponse, data)
