"""This component updates the camera API and subscription."""
import logging

from reolink.camera_api import Api
from reolink.subscription_manager import Manager

from .const import EVENT_DATA_RECEIVED, SESSION_RENEW_THRESHOLD

_LOGGER = logging.getLogger(__name__)


class ReolinkBase:
    """The implementation of the Reolink IP base class."""

    def __init__(
        self, hass, host, port, username, password
    ):  # pylint: disable=too-many-arguments
        """Initialize a Reolink camera."""
        self._username = username
        self._password = password

        self._api = Api(host, port, username, password)
        self._sman = None
        self._webhook_url = None
        self._hass = hass
        self.sync_functions = list()
        self.motion_detection_state = True
        self.motion_off_delay = 60

    @property
    def event_id(self):
        """Create the event ID string."""
        event_id = self._api.mac_address.replace(":", "")
        return f"{EVENT_DATA_RECEIVED}-{event_id}"

    @property
    def api(self):
        """Return the API object."""
        return self._api

    @property
    def sman(self):
        """Return the Session Manager object."""
        return self._sman

    async def connect_api(self):
        """Connect to the Reolink API and fetch initial dataset."""
        if not await self._api.get_settings():
            return False
        if not await self._api.get_states():
            return False

        await self._api.is_admin()
        return True

    async def update_api(self):
        """Call the API of the camera device to update the settings and states."""
        await self._api.get_settings()
        await self._api.get_states()

    async def disconnect_api(self):
        """Disconnect from the API, so the connection will be released."""
        await self._api.logout()

    async def subscribe(self, webhook_url):
        """Subscribe to motion events and set the webhook as callback."""
        self._webhook_url = webhook_url

        if not self._api.session_active:
            _LOGGER.error("Please connect with the camera API before subscribing")
            return False

        self._sman = Manager(
            self._api.host, self._api.onvif_port, self._username, self._password
        )
        if not await self._sman.subscribe(self._webhook_url):
            return False

        _LOGGER.info(
            "Host %s subscribed successfully to webhook %s!",
            self._api.host,
            webhook_url,
        )
        return True

    async def renew(self):
        """Renew the subscription of the motion events (lease time is set to 15 minutes)."""
        if self._sman.renewtimer <= SESSION_RENEW_THRESHOLD:
            if not await self._sman.renew():
                _LOGGER.error(
                    "Host %s error renewing the Reolink subscription",
                    self._api.host,
                )
                await self._sman.subscribe(self._webhook_url)

    async def unsubscribe(self):
        """Unsubscribe from the motion events."""
        return await self._sman.unsubscribe()

    async def stop(self):
        """Disconnect the APi and unsubscribe."""
        await self.disconnect_api()
        await self.unsubscribe()
        for func in self.sync_functions:
            await self._hass.async_add_executor_job(func)
