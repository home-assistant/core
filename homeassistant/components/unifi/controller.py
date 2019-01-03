"""UniFi Controller abstraction."""

import asyncio
import async_timeout

from aiohttp import CookieJar

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.helpers import aiohttp_client

from .const import CONF_CONTROLLER, CONF_POE_CONTROL, LOGGER
from .errors import AuthenticationRequired, CannotConnect


class UniFiController:
    """Manages a single UniFi Controller."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.available = True
        self.api = None
        self.progress = None
        self._cancel_retry_setup = None

    @property
    def host(self):
        """Return the host of this controller."""
        return self.config_entry.data[CONF_CONTROLLER][CONF_HOST]

    @property
    def mac(self):
        """Return the mac address of this controller."""
        for client in self.api.clients.values():
            if self.host == client.ip:
                return client.mac
        return None

    async def async_setup(self, tries=0):
        """Set up a UniFi controller."""
        hass = self.hass

        try:
            self.api = await get_controller(
                self.hass, **self.config_entry.data[CONF_CONTROLLER])
            await self.api.initialize()

        except CannotConnect:
            retry_delay = 2 ** (tries + 1)
            LOGGER.error("Error connecting to the UniFi controller. Retrying "
                         "in %d seconds", retry_delay)

            async def retry_setup(_now):
                """Retry setup."""
                if await self.async_setup(tries + 1):
                    # This feels hacky, we should find a better way to do this
                    self.config_entry.state = config_entries.ENTRY_STATE_LOADED

            self._cancel_retry_setup = hass.helpers.event.async_call_later(
                retry_delay, retry_setup)

            return False

        except Exception:  # pylint: disable=broad-except
            LOGGER.error(
                'Unknown error connecting with UniFi controller.')
            return False

        if self.config_entry.data[CONF_POE_CONTROL]:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    self.config_entry, 'switch'))

        return True

    async def async_reset(self):
        """Reset this controller to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        # If we have a retry scheduled, we were never setup.
        if self._cancel_retry_setup is not None:
            self._cancel_retry_setup()
            self._cancel_retry_setup = None
            return True

        # If the authentication was wrong.
        if self.api is None:
            return True

        if self.config_entry.data[CONF_POE_CONTROL]:
            return await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, 'switch')
        return True


async def get_controller(
        hass, host, username, password, port, site, verify_ssl):
    """Create a controller object and verify authentication."""
    import aiounifi

    if verify_ssl:
        session = aiohttp_client.async_get_clientsession(hass)
    else:
        session = aiohttp_client.async_create_clientsession(
            hass, verify_ssl=verify_ssl, cookie_jar=CookieJar(unsafe=True))

    controller = aiounifi.Controller(
        host, username=username, password=password, port=port, site=site,
        websession=session
    )

    try:
        with async_timeout.timeout(5):
            await controller.login()
        return controller

    except aiounifi.Unauthorized:
        LOGGER.warning("Connected to UniFi at %s but not registered.", host)
        raise AuthenticationRequired

    except (asyncio.TimeoutError, aiounifi.RequestError):
        LOGGER.error("Error connecting to the UniFi controller at %s", host)
        raise CannotConnect

    except aiounifi.AiounifiException:
        LOGGER.exception('Unknown UniFi communication error occurred')
        raise AuthenticationRequired
