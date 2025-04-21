"""The FireServiceRota integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyfireservicerota import (
    ExpiredTokenError,
    FireServiceRota,
    FireServiceRotaIncidents,
    InvalidAuthError,
    InvalidTokenError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, WSS_BWRURL

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

type FireServiceConfigEntry = ConfigEntry[FireServiceUpdateCoordinator]


class FireServiceUpdateCoordinator(DataUpdateCoordinator[dict | None]):
    """Data update coordinator for FireServiceRota."""

    config_entry: FireServiceConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: FireServiceRotaClient,
        entry: FireServiceConfigEntry,
    ) -> None:
        """Initialize the FireServiceRota DataUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="duty binary sensor",
            config_entry=entry,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )

        self.client = client

    async def _async_update_data(self) -> dict | None:
        """Get the latest availability data."""
        return await self.client.async_update()


class FireServiceRotaOauth:
    """Handle authentication tokens."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, fsr: FireServiceRota
    ) -> None:
        """Initialize the oauth object."""
        self._hass = hass
        self._entry = entry

        self._url = entry.data[CONF_URL]
        self._username = entry.data[CONF_USERNAME]
        self._fsr = fsr

    async def async_refresh_tokens(self) -> bool:
        """Refresh tokens and update config entry."""
        _LOGGER.debug("Refreshing authentication tokens after expiration")

        try:
            token_info = await self._hass.async_add_executor_job(
                self._fsr.refresh_tokens
            )

        except (InvalidAuthError, InvalidTokenError) as err:
            raise ConfigEntryAuthFailed(
                "Error refreshing tokens, triggered reauth workflow"
            ) from err

        _LOGGER.debug("Saving new tokens in config entry")
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={
                "auth_implementation": DOMAIN,
                CONF_URL: self._url,
                CONF_USERNAME: self._username,
                CONF_TOKEN: token_info,
            },
        )

        return True


class FireServiceRotaWebSocket:
    """Define a FireServiceRota websocket manager object."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the websocket object."""
        self._hass = hass
        self._entry = entry

        self._fsr_incidents = FireServiceRotaIncidents(on_incident=self._on_incident)
        self.incident_data = None

    def _construct_url(self) -> str:
        """Return URL with latest access token."""
        return WSS_BWRURL.format(
            self._entry.data[CONF_URL], self._entry.data[CONF_TOKEN]["access_token"]
        )

    def _on_incident(self, data) -> None:
        """Received new incident, update data."""
        _LOGGER.debug("Received new incident via websocket: %s", data)
        self.incident_data = data
        dispatcher_send(self._hass, f"{DOMAIN}_{self._entry.entry_id}_update")

    def start_listener(self) -> None:
        """Start the websocket listener."""
        _LOGGER.debug("Starting incidents listener")
        self._fsr_incidents.start(self._construct_url())

    def stop_listener(self) -> None:
        """Stop the websocket listener."""
        _LOGGER.debug("Stopping incidents listener")
        self._fsr_incidents.stop()


class FireServiceRotaClient:
    """Getting the latest data from fireservicerota."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the data object."""
        self._hass = hass
        self._entry = entry

        self._url = entry.data[CONF_URL]
        self._tokens = entry.data[CONF_TOKEN]

        self.entry_id = entry.entry_id
        self.unique_id = entry.unique_id

        self.token_refresh_failure = False
        self.incident_id = None
        self.on_duty = False

        self.fsr = FireServiceRota(base_url=self._url, token_info=self._tokens)

        self.oauth = FireServiceRotaOauth(
            self._hass,
            self._entry,
            self.fsr,
        )

        self.websocket = FireServiceRotaWebSocket(self._hass, self._entry)

    async def setup(self) -> None:
        """Set up the data client."""
        await self._hass.async_add_executor_job(self.websocket.start_listener)

    async def update_call(self, func, *args):
        """Perform update call and return data."""
        if self.token_refresh_failure:
            return None

        try:
            return await self._hass.async_add_executor_job(func, *args)
        except (ExpiredTokenError, InvalidTokenError):
            await self._hass.async_add_executor_job(self.websocket.stop_listener)
            self.token_refresh_failure = True

            if await self.oauth.async_refresh_tokens():
                self.token_refresh_failure = False
                await self._hass.async_add_executor_job(self.websocket.start_listener)

                return await self._hass.async_add_executor_job(func, *args)

    async def async_update(self) -> dict | None:
        """Get the latest availability data."""
        data = await self.update_call(
            self.fsr.get_availability, str(self._hass.config.time_zone)
        )

        if not data:
            return None

        self.on_duty = bool(data.get("available"))

        _LOGGER.debug("Updated availability data: %s", data)
        return data

    async def async_response_update(self) -> dict | None:
        """Get the latest incident response data."""

        if not self.incident_id:
            return None

        _LOGGER.debug("Updating response data for incident id %s", self.incident_id)

        return await self.update_call(self.fsr.get_incident_response, self.incident_id)

    async def async_set_response(self, value) -> None:
        """Set incident response status."""

        if not self.incident_id:
            return

        _LOGGER.debug(
            "Setting incident response for incident id '%s' to state '%s'",
            self.incident_id,
            value,
        )

        await self.update_call(self.fsr.set_incident_response, self.incident_id, value)

    async def async_stop_listener(self) -> None:
        """Stop listener."""
        await self._hass.async_add_executor_job(self.websocket.stop_listener)
