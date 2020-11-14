"""This component updates the camera API and subscription."""
import logging

from reolink.cameraApi import api
from reolink.subscriptionManager import manager

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
        """Create the event ID string."""
        eventId = self._api.mac_address.replace(":", "")
        return f"{EVENT_DATA_RECEIVED}-{eventId}"

    @property
    def api(self):
        """Return the API object."""
        return self._api

    @property
    def sman(self):
        """Return the Session Manager object."""
        return self._sman

    async def connectApi(self):
        """Connect to the Reolink API and fetch initial dataset."""
        if not await self._api.get_settings():
            return False
        if not await self._api.get_states():
            return False

        await self._api.isAdmin()
        return True

    async def updateApi(self):
        """Call the API of the camera device to update the settings and states."""
        await self._api.get_settings()
        await self._api.get_states()

    async def disconnectApi(self):
        """Disconnect from the API, so the connection will be released."""
        await self._api.logout()

    async def subscribe(self, webhookUrl):
        """subscribe to motion events and set the webhook as callback."""
        self._webhookUrl = webhookUrl

        if not self._api.session_active:
            _LOGGER.error("Please connect with the camera API before subscribing")
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
        """Renew the subscription of the motion events (lease time is set to 15 minutes)."""
        if self._sman.renewTimer <= SESSION_RENEW_THRESHOLD:
            if not (await self._sman.renew()):
                _LOGGER.error(
                    f"Host {self._api.host} error renewing the Reolink subscription"
                )
                await self._sman.subscribe(self._webhookUrl)

    async def unsubscribe(self):
        """Unsubscribe from the motion events."""
        return await self._sman.unsubscribe()

    async def stop(self):
        """Disconnect the APi and unsubscribe."""
        await self.disconnectApi()
        await self.unsubscribe()
