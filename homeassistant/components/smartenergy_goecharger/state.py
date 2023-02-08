"""go-e Charger Cloud state (coordinator) management."""

import logging

import aiohttp
from goechargerv2.goecharger import GoeChargerApi

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API, CHARGERS_API, DOMAIN, INIT_STATE, OFFLINE, ONLINE, STATUS
from .controller import fetch_status

_LOGGER: logging.Logger = logging.getLogger(__name__)


def init_state(name: str, url: str, token: str) -> dict:
    """Initialize the state with go-e Charger Cloud API and static values."""

    return {
        CONF_NAME: name,
        API: GoeChargerApi(url, token, wait=True),
    }


class StateFetcher:
    """
    Representation of the coordinator state handling.

    Whenever the coordinator is triggered, it will call the APIs and update status data.
    """

    coordinator: DataUpdateCoordinator

    def __init__(self, hass: HomeAssistant) -> None:
        """Construct controller with hass property."""
        self._hass: HomeAssistant = hass

    async def fetch_states(self) -> dict:
        """
        Fetch go-e Charger Cloud car status via API.

        Fetched data will be enhanced with the:
        - friendly name of the charger.
        """

        _LOGGER.debug("Updating the go-e Charger Cloud coordinator data")

        chargers_api: GoeChargerApi = self._hass.data[DOMAIN][INIT_STATE][CHARGERS_API]
        current_data: dict = self.coordinator.data if self.coordinator.data else {}
        _LOGGER.debug("Current go-e Charger Cloud coordinator data=%s", current_data)

        updated_data: dict = {}

        for charger_name in chargers_api.keys():
            try:
                fetched_data: dict = await fetch_status(self._hass, charger_name)

                if (
                    fetched_data.get("success", None) is False
                    and fetched_data.get("msg", None) == "Wallbox is offline"
                ):
                    updated_data[charger_name] = (
                        current_data if not current_data else current_data[charger_name]
                    )
                    updated_data[charger_name][STATUS] = OFFLINE
                else:
                    updated_data[charger_name] = fetched_data
                    updated_data[charger_name][STATUS] = ONLINE

                updated_data[charger_name][CONF_NAME] = chargers_api[charger_name][
                    CONF_NAME
                ]
            except (aiohttp.ClientError, RuntimeError):
                _LOGGER.error("Can't connect to the device %s", charger_name)
                updated_data[charger_name] = (
                    current_data if not current_data else current_data[charger_name]
                )
                updated_data[charger_name][STATUS] = OFFLINE

        _LOGGER.debug("Updated go-e Charger Cloud coordinator data=%s", updated_data)

        return updated_data
