"""The FireServiceRota integration."""
import asyncio
from datetime import timedelta
import logging

from pyfireservicerota import (
    ExpiredTokenError,
    FireServiceRota,
    FireServiceRotaIncidents,
    InvalidAuthError,
    InvalidTokenError,
)

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import Throttle

from .const import DOMAIN, NOTIFICATION_AUTH_ID, NOTIFICATION_AUTH_TITLE, WSS_BWRURL

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = {SENSOR_DOMAIN}


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the FireServiceRota component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FireServiceRota from a config entry."""
    coordinator = FSRDataUpdateCoordinator(hass, entry)
    await coordinator.async_update()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in SUPPORTED_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload FireServiceRota config entry."""
    hass.data[DOMAIN][entry.entry_id].stop_listener()

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in SUPPORTED_PLATFORMS
            ]
        )
    )

    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok


class FSRDataUpdateCoordinator:
    """Getting the latest data from fireservicerota."""

    def __init__(self, hass, entry):
        """Initialize the data object."""
        self._hass = hass
        self._entry = entry

        self._url = entry.data[CONF_URL]
        self._tokens = entry.data[CONF_TOKEN]

        self.availability_data = None
        self.incident_data = None
        self.incident_id = None
        self.response_data = None

        self.fsr_avail = FireServiceRota(
            base_url=f"https://{self._url}", token_info=self._tokens
        )

        self.fsr_incidents = FireServiceRotaIncidents(on_incident=self.on_incident)

        self.start_listener()

    def construct_url(self) -> str:
        """Return url with latest config values."""
        return WSS_BWRURL.format(
            self._entry.data[CONF_URL], self._entry.data[CONF_TOKEN]["access_token"]
        )

    def on_incident(self, data) -> None:
        """Update the current data."""
        _LOGGER.debug("Got data from websocket listener: %s", data)
        self.incident_data = data

        async_dispatcher_send(self._hass, f"{DOMAIN}_{self._entry.entry_id}_update")

    def start_listener(self) -> None:
        """Start the websocket listener."""
        _LOGGER.debug("Starting incidents listener")
        self.fsr_incidents.start(self.construct_url())

    def stop_listener(self) -> None:
        """Stop the websocket listener."""
        _LOGGER.debug("Stopping incidents listener")
        self.fsr_incidents.stop()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Get the latest availability data."""
        try:
            self.availability_data = await self._hass.async_add_executor_job(
                self.fsr_avail.get_availability, str(self._hass.config.time_zone)
            )
            _LOGGER.debug("Updating availability data")
        except (ExpiredTokenError, InvalidTokenError):
            await self.async_refresh_tokens()

    async def async_response_update(self) -> None:
        """Get the latest incident response data."""
        if self.incident_data is None:
            return

        self.incident_id = self.incident_data.get("id")
        _LOGGER.debug("Incident id: %s", self.incident_id)
        try:
            self.response_data = await self._hass.async_add_executor_job(
                self.fsr_avail.get_incident_response, self.incident_id
            )
            _LOGGER.debug("Updating incident response data")
        except (ExpiredTokenError, InvalidTokenError):
            await self.async_refresh_tokens()

    async def async_set_response(self, incident_id, value) -> None:
        """Set incident response status."""
        try:
            await self._hass.async_add_executor_job(
                self.fsr_avail.set_incident_response, incident_id, value
            )
            _LOGGER.debug("Setting incident response status")
        except (ExpiredTokenError, InvalidTokenError):
            await self.async_refresh_tokens()

    async def async_refresh_tokens(self) -> bool:
        """Refresh tokens and update config entry."""
        self.stop_listener()

        _LOGGER.debug("Refreshing authentication tokens after expiration")
        try:
            token_info = await self._hass.async_add_executor_job(
                self.fsr_avail.refresh_tokens
            )
        except (InvalidAuthError, InvalidTokenError):
            _LOGGER.error("Error occurred while refreshing authentication tokens")
            self._hass.components.persistent_notification.async_create(
                "Cannot refresh tokens, you need to re-add this integration to generate new ones.",
                title=NOTIFICATION_AUTH_TITLE,
                notification_id=NOTIFICATION_AUTH_ID,
            )

            return False

        _LOGGER.debug("Saving new tokens in config entry")
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={
                "auth_implementation": DOMAIN,
                CONF_URL: self._url,
                CONF_TOKEN: token_info,
            },
        )
        self.start_listener()

        return True
