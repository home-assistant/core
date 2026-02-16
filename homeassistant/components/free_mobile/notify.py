"""Support for Free Mobile SMS platform."""

from http import HTTPStatus
import logging

from freesms import FreeClient

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Free Mobile SMS notification service."""
    async_add_entities([FreeSMSNotifyEntity(config_entry)])


class FreeSMSNotifyEntity(NotifyEntity):
    """Implement a notification service for the Free Mobile SMS service."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the service."""
        # Use the client from runtime_data
        self._config_entry = config_entry

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to the Free Mobile user cell."""
        # Get the client from runtime_data
        client: FreeClient = self._config_entry.runtime_data
        await self.hass.async_add_executor_job(self._send_sms, message, client)

    def _send_sms(self, message: str, client: FreeClient) -> None:
        """Send SMS via Free Mobile API (blocking call)."""
        resp = client.send_sms(message)

        if resp.status_code == HTTPStatus.BAD_REQUEST:
            _LOGGER.error("At least one parameter is missing")
        elif resp.status_code == HTTPStatus.FORBIDDEN:
            _LOGGER.error("Wrong Username/Password")
        elif resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            _LOGGER.error("Server error, try later")
        elif resp.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            _LOGGER.error("Too many SMS sent in a short time")
