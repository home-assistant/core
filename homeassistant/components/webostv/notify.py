"""Support for LG WebOS TV notification service."""
import asyncio
import logging

from aiopylgtv import PyLGTVCmdException, PyLGTVPairException
from websockets.exceptions import ConnectionClosed

from homeassistant.components.notify import ATTR_DATA, BaseNotificationService
from homeassistant.const import CONF_ICON, CONF_NAME

from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_service(hass, config, discovery_info=None):
    """Return the notify service."""
    if discovery_info is None:
        return None
    name = discovery_info.get(CONF_NAME)
    client = hass.data[DOMAIN][discovery_info[ATTR_CONFIG_ENTRY_ID]]

    return LgWebOSNotificationService(client, name)


class LgWebOSNotificationService(BaseNotificationService):
    """Implement the notification service for LG WebOS TV."""

    def __init__(self, client, name):
        """Initialize the service."""
        self._name = name
        self._client = client

    async def async_send_message(self, message="", **kwargs):
        """Send a message to the tv."""
        try:
            data = kwargs.get(ATTR_DATA)
            icon_path = data.get(CONF_ICON, "") if data else None
            if not self._client.is_connected():
                await self._client.connect()
            await self._client.send_message(message, icon_path=icon_path)
        except PyLGTVPairException:
            _LOGGER.error("Pairing with TV failed")
        except FileNotFoundError:
            _LOGGER.error("Icon %s not found", icon_path)
        except (
            OSError,
            ConnectionClosed,
            ConnectionRefusedError,
            asyncio.TimeoutError,
            asyncio.CancelledError,
            PyLGTVCmdException,
        ):
            _LOGGER.error("TV unreachable")
