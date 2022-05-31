"""The Glances component."""
from datetime import timedelta
import logging
from typing import Any

from glances_api import Glances, exceptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Glances from config entry."""
    api = get_api(hass, dict(config_entry.data))
    coordinator = GlancesDataUpdateCoordinator(hass, config_entry, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


class GlancesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Get the latest data from Glances api."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: Glances
    ) -> None:
        """Initialize the Glances data."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        self.api = api
        super().__init__(
            self.hass,
            _LOGGER,
            name=f"{DOMAIN} - {self.host}",
            update_interval=timedelta(
                seconds=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                )
            ),
        )

    @property
    def host(self) -> str:
        """Return client host."""
        return self.config_entry.data[CONF_HOST]

    async def _async_update_data(self) -> dict[str, Any]:
        """Get the latest data from the Glances REST API."""
        try:
            await self.api.get_data("all")
        except exceptions.GlancesApiError as err:
            raise UpdateFailed from err
        return self.api.data


def get_api(hass: HomeAssistant, entry: dict[str, Any]) -> Glances:
    """Return the api from glances_api."""
    params = entry.copy()
    params.pop(CONF_NAME, None)
    verify_ssl = params.pop(CONF_VERIFY_SSL, True)
    httpx_client = get_async_client(hass, verify_ssl=verify_ssl)
    return Glances(httpx_client=httpx_client, **params)
