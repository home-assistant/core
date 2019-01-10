"""Access point for the HomematicIP Cloud component."""
import asyncio
import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    COMPONENTS, HMIPC_AUTHTOKEN, HMIPC_HAPID, HMIPC_NAME, HMIPC_PIN)
from .errors import HmipcConnectionError

_LOGGER = logging.getLogger(__name__)


class HomematicipAuth:
    """Manages HomematicIP client registration."""

    def __init__(self, hass, config):
        """Initialize HomematicIP Cloud client registration."""
        self.hass = hass
        self.config = config
        self.auth = None

    async def async_setup(self):
        """Connect to HomematicIP for registration."""
        try:
            self.auth = await self.get_auth(
                self.hass,
                self.config.get(HMIPC_HAPID),
                self.config.get(HMIPC_PIN)
            )
            return True
        except HmipcConnectionError:
            return False

    async def async_checkbutton(self):
        """Check blue butten has been pressed."""
        from homematicip.base.base_connection import HmipConnectionError

        try:
            await self.auth.isRequestAcknowledged()
            return True
        except HmipConnectionError:
            return False

    async def async_register(self):
        """Register client at HomematicIP."""
        from homematicip.base.base_connection import HmipConnectionError

        try:
            authtoken = await self.auth.requestAuthToken()
            await self.auth.confirmAuthToken(authtoken)
            return authtoken
        except HmipConnectionError:
            return False

    async def get_auth(self, hass, hapid, pin):
        """Create a HomematicIP access point object."""
        from homematicip.aio.auth import AsyncAuth
        from homematicip.base.base_connection import HmipConnectionError

        auth = AsyncAuth(hass.loop, async_get_clientsession(hass))
        try:
            await auth.init(hapid)
            if pin:
                auth.pin = pin
            await auth.connectionRequest('HomeAssistant')
        except HmipConnectionError:
            return False
        return auth


class HomematicipHAP:
    """Manages HomematicIP HTTP and WebSocket connection."""

    def __init__(self, hass, config_entry):
        """Initialize HomematicIP Cloud connection."""
        self.hass = hass
        self.config_entry = config_entry
        self.home = None

        self._ws_close_requested = False
        self._retry_task = None
        self._tries = 0
        self._accesspoint_connected = True
        self._retry_setup = None

    async def async_setup(self, tries=0):
        """Initialize connection."""
        try:
            self.home = await self.get_hap(
                self.hass,
                self.config_entry.data.get(HMIPC_HAPID),
                self.config_entry.data.get(HMIPC_AUTHTOKEN),
                self.config_entry.data.get(HMIPC_NAME)
            )
        except HmipcConnectionError:
            retry_delay = 2 ** min(tries, 8)
            _LOGGER.error("Error connecting to HomematicIP with HAP %s. "
                          "Retrying in %d seconds",
                          self.config_entry.data.get(HMIPC_HAPID), retry_delay)

            async def retry_setup(_now):
                """Retry setup."""
                if await self.async_setup(tries + 1):
                    self.config_entry.state = config_entries.ENTRY_STATE_LOADED

            self._retry_setup = self.hass.helpers.event.async_call_later(
                retry_delay, retry_setup)

            return False

        _LOGGER.info("Connected to HomematicIP with HAP %s",
                     self.config_entry.data.get(HMIPC_HAPID))

        for component in COMPONENTS:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, component)
            )
        return True

    @callback
    def async_update(self, *args, **kwargs):
        """Async update the home device.

        Triggered when the HMIP HOME_CHANGED event has fired.
        There are several occasions for this event to happen.
        We are only interested to check whether the access point
        is still connected. If not, device state changes cannot
        be forwarded to hass. So if access point is disconnected all devices
        are set to unavailable.
        """
        if not self.home.connected:
            _LOGGER.error(
                "HMIP access point has lost connection with the cloud")
            self._accesspoint_connected = False
            self.set_all_to_unavailable()
        elif not self._accesspoint_connected:
            # Now the HOME_CHANGED event has fired indicating the access
            # point has reconnected to the cloud again.
            # Explicitly getting an update as device states might have
            # changed during access point disconnect."""

            job = self.hass.async_create_task(self.get_state())
            job.add_done_callback(self.get_state_finished)

    async def get_state(self):
        """Update HMIP state and tell Home Assistant."""
        await self.home.get_current_state()
        self.update_all()

    def get_state_finished(self, future):
        """Execute when get_state coroutine has finished."""
        from homematicip.base.base_connection import HmipConnectionError

        try:
            future.result()
        except HmipConnectionError:
            # Somehow connection could not recover. Will disconnect and
            # so reconnect loop is taking over.
            _LOGGER.error(
                "Updating state after HMIP access point reconnect failed")
            self.hass.async_create_task(self.home.disable_events())

    def set_all_to_unavailable(self):
        """Set all devices to unavailable and tell Home Assistant."""
        for device in self.home.devices:
            device.unreach = True
        self.update_all()

    def update_all(self):
        """Signal all devices to update their state."""
        for device in self.home.devices:
            device.fire_update_event()

    async def async_connect(self):
        """Start WebSocket connection."""
        from homematicip.base.base_connection import HmipConnectionError

        tries = 0
        while True:
            retry_delay = 2 ** min(tries, 8)

            try:
                await self.home.get_current_state()
                hmip_events = await self.home.enable_events()
                tries = 0
                await hmip_events
            except HmipConnectionError:
                _LOGGER.error("Error connecting to HomematicIP with HAP %s. "
                              "Retrying in %d seconds",
                              self.config_entry.data.get(HMIPC_HAPID),
                              retry_delay)

            if self._ws_close_requested:
                break
            self._ws_close_requested = False
            tries += 1

            try:
                self._retry_task = self.hass.async_create_task(asyncio.sleep(
                    retry_delay, loop=self.hass.loop))
                await self._retry_task
            except asyncio.CancelledError:
                break

    async def async_reset(self):
        """Close the websocket connection."""
        self._ws_close_requested = True
        if self._retry_setup is not None:
            self._retry_setup.cancel()
        if self._retry_task is not None:
            self._retry_task.cancel()
        await self.home.disable_events()
        _LOGGER.info("Closed connection to HomematicIP cloud server")
        for component in COMPONENTS:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, component)
        return True

    async def get_hap(self, hass, hapid, authtoken, name):
        """Create a HomematicIP access point object."""
        from homematicip.aio.home import AsyncHome
        from homematicip.base.base_connection import HmipConnectionError

        home = AsyncHome(hass.loop, async_get_clientsession(hass))

        home.name = name
        home.label = 'Access Point'
        home.modelType = 'HmIP-HAP'

        home.set_auth_token(authtoken)
        try:
            await home.init(hapid)
            await home.get_current_state()
        except HmipConnectionError:
            raise HmipcConnectionError
        home.on_update(self.async_update)
        hass.loop.create_task(self.async_connect())

        return home
