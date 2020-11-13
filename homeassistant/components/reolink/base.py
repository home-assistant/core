"""This component provides basic support for Reolink IP cameras."""
import logging

import reolink
from homeassistant.const import (ATTR_ENTITY_ID, CONF_HOST, CONF_NAME,
                                 CONF_PASSWORD, CONF_PORT, CONF_USERNAME)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from reolink.cameraApi import api
from reolink.subscriptionManager import manager

from .const import DOMAIN  # pylint:disable=unused-import
from .const import EVENT_DATA_RECEIVED, SESSION_RENEW_THRESHOLD

_LOGGER = logging.getLogger(__name__)


class ReolinkBase:
    """The implementation of the Reolink IP base class."""

    def __init__(self, hass, host, port, username, password):
        """Initialize a Reolink camera."""
        self._username = username
        self._password = password

        self._api = api(host, port, username, password)
        self._sman = None
        self._webhookUrl = None
        self._hass = hass

    @property
    def eventId(self):
        return f"{EVENT_DATA_RECEIVED}-{self._api.mac_address.replace(':', '')}"

    async def connectApi(self):
        """Connect to the Reolink API and fetch initial dataset."""

        if not await self._api.get_settings():
            return False
        if not await self._api.get_states():
            return False

        await self._api.isAdmin()
        return True

    async def updateApi(self):
        await self._api.get_settings()
        await self._api.get_states()

    async def disconnectApi(self):
        await self._api.logout()

    async def subscribe(self, webhookUrl):
        self._webhookUrl = webhookUrl

        if not self._api.session_active:
            _LOGGER.error(f"Please connect with the camera API before subscribing")
            return False

        self._sman = manager(
            self._api.host, self._api.onvif_port, self._username, self._password
        )
        if not (await self._sman.subscribe(self._webhookUrl)):
            return False

        _LOGGER.info(
            f"Host {self._api.host} got a Reolink subscription manager: {self._sman._manager_url}"
        )
        return True

    async def renew(self):
        if self._sman.renewTimer <= SESSION_RENEW_THRESHOLD:
            if not (await self._sman.renew()):
                _LOGGER.error(
                    "Host {self._api.host} error renewing the Reolink subscription"
                )
                await self._sman.subscribe(self._webhookUrl)

    async def unsubscribe(self):
        return await self._sman.unsubscribe()

    async def stop(self):
        await self.disconnectApi()
        await self.unsubscribe()
