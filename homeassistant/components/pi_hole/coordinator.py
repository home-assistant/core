"""Coordinator for the Pi-hole integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from hole import HoleV5, HoleV6
from hole.exceptions import HoleError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MIN_TIME_BETWEEN_UPDATES, VERSION_6_RESPONSE_TO_5_ERROR

_LOGGER = logging.getLogger(__name__)


@dataclass
class PiHoleData:
    """Runtime data definition."""

    api: HoleV5 | HoleV6
    coordinator: PiHoleUpdateCoordinator
    api_version: int


type PiHoleConfigEntry = ConfigEntry[PiHoleData]


class PiHoleUpdateCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for Pi-hole data updates."""

    config_entry: PiHoleConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: HoleV5 | HoleV6,
        config_entry: PiHoleConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.data[CONF_NAME],
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self._api = api
        self._name = config_entry.data[CONF_NAME]
        self._host = config_entry.data[CONF_HOST]

    async def _async_update_data(self) -> None:
        """Fetch data from the Pi-hole API."""
        try:
            await self._api.get_data()
            await self._api.get_versions()
            if "error" in (response := self._api.data):
                match response["error"]:
                    case {
                        "key": key,
                        "message": message,
                        "hint": hint,
                    } if (
                        key == VERSION_6_RESPONSE_TO_5_ERROR["key"]
                        and message == VERSION_6_RESPONSE_TO_5_ERROR["message"]
                        and hint.startswith("The API is hosted at ")
                        and "/admin/api" in hint
                    ):
                        _LOGGER.warning(
                            "Pi-hole API v6 returned an error that is expected when using v5 endpoints please re-configure your authentication"
                        )
                        raise ConfigEntryAuthFailed
        except HoleError as err:
            if str(err) == "Authentication failed: Invalid password":
                raise ConfigEntryAuthFailed(
                    f"Pi-hole {self._name} at host {self._host}, reported an invalid password"
                ) from err
            raise UpdateFailed(
                f"Pi-hole {self._name} at host {self._host}, update failed with HoleError: {err}"
            ) from err
        if not isinstance(self._api.data, dict):
            raise ConfigEntryAuthFailed(
                f"Pi-hole {self._name} at host {self._host}, returned an unexpected response: {self._api.data}, assuming authentication failed"
            )
