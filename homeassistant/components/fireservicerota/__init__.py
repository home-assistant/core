"""The FireServiceRota integration."""
import asyncio
from datetime import timedelta
import logging

from pyfireservicerota import (
    ExpiredTokenError,
    FireServiceRota,
    InvalidAuthError,
    InvalidTokenError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

from .const import DOMAIN, NOTIFICATION_AUTH_ID, NOTIFICATION_AUTH_TITLE, PLATFORMS

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)
async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the FireServiceRota component."""
    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up FireServiceRota from a config entry."""
    data = FireServiceRotaData(hass, entry)
    await data.async_update()

    hass.data[DOMAIN] = data

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


class FireServiceRotaData:
    """Getting the latest data from fireservicerota."""

    def __init__(self, hass, entry):
        """Initialize the data object."""
        self._hass = hass
        self._entry = entry
        self._url = entry.data[CONF_URL]
        self._tokens = entry.data[CONF_TOKEN]

        self.fsr = FireServiceRota(
            base_url=f"https://{self._url}", token_info=self._tokens
        )
        self.availability_data = None
        self.incident_data = None
        self.incident_id = None
        self.response_data = None

    def set_incident_data(self, data):
        """Set incident data from websocket."""
        self.incident_data = data

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest availability data."""
        try:
            self.availability_data = await self._hass.async_add_executor_job(
                self.fsr.get_availability
            )
            _LOGGER.debug("Updating availability data")
        except ExpiredTokenError:
            _LOGGER.debug("Refreshing expired tokens")
            await self.async_refresh()

    async def async_response_update(self):
        """Get the latest incident response data."""
        if self.incident_data:
            self.incident_id = self.incident_data.get("id")
            _LOGGER.debug("Incident id: %s", self.incident_id)
            try:
                self.response_data = await self._hass.async_add_executor_job(
                    self.fsr.get_incident_response, self.incident_id
                )
                _LOGGER.debug("Updating incident response data")
            except ExpiredTokenError:
                _LOGGER.debug("Refreshing expired tokens")
                await self.async_refresh()

    async def async_set_response(self, incident_id, value):
        """Set incident response status."""
        try:
            await self._hass.async_add_executor_job(
                self.fsr.set_incident_response, incident_id, value
            )
            _LOGGER.debug("Setting incident response status")
        except ExpiredTokenError:
            _LOGGER.debug("Refreshing expired tokens")
            await self.async_refresh()

    async def async_refresh(self) -> bool:
        """Refresh tokens and update config entry."""
        _LOGGER.debug("Refreshing authentication tokens")
        try:
            token_info = await self._hass.async_add_executor_job(
                self.fsr.refresh_tokens
            )
        except (InvalidAuthError, InvalidTokenError):
            _LOGGER.error("Error occurred while refreshing authentication tokens")
            self._hass.components.persistent_notification.async_create(
                "Cannot refresh tokens, you need to re-add this integration and login to generate new ones.",
                title=NOTIFICATION_AUTH_TITLE,
                notification_id=NOTIFICATION_AUTH_ID,
            )
            return False

        _LOGGER.debug("Saving new tokens to config entry")
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={
                "auth_implementation": DOMAIN,
                CONF_URL: self._url,
                CONF_TOKEN: token_info,
            },
        )
        return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data.pop(DOMAIN)

    tasks = []
    for platform in PLATFORMS:
        tasks.append(hass.config_entries.async_forward_entry_unload(entry, platform))

    return all(await asyncio.gather(*tasks))
