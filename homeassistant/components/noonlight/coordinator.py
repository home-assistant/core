"""Reachability coordinator for the Noonlight integration."""

from datetime import timedelta
import logging

from noonlight_dispatch import NoonlightClient, NoonlightError, NoonlightResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, POLL_INTERVAL, PROBE_ALARM_ID

_LOGGER = logging.getLogger(__name__)

type NoonlightConfigEntry = ConfigEntry[NoonlightCoordinator]


class NoonlightCoordinator(DataUpdateCoordinator[bool]):
    """Periodically probe Noonlight for reachability and a valid token."""

    config_entry: NoonlightConfigEntry

    def __init__(self, hass: HomeAssistant, entry: NoonlightConfigEntry) -> None:
        """Initialise the coordinator for ``entry``."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.api = NoonlightClient(get_async_client(hass), entry.data[CONF_API_TOKEN])

    async def _async_update_data(self) -> bool:
        """Probe Noonlight and report whether it is reachable + authorized.

        A GET on a bogus alarm id has no side effects: a 404 means we are
        reachable + authorized, while a 401/403, a 5xx/429, or a transport
        error all mean the API is not currently usable. The probe never raises,
        so the binary sensor always reflects the latest known reachability.
        """
        try:
            await self.api.get_alarm_status(PROBE_ALARM_ID)
        except NoonlightResponseError as err:
            # Only a 404 on the bogus id proves reachable + authorized.
            return err.status_code == 404
        except NoonlightError as err:
            _LOGGER.debug("Noonlight reachability probe failed: %s", err)
            return False
        # A 2xx is unlikely for a bogus id, but still means reachable + authed.
        return True
