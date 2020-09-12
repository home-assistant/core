"""Support for Google Domains."""
import asyncio
import logging

import aiohttp
import async_timeout

from homeassistant.const import CONF_DOMAIN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .consts import DEFAULT_TIMEOUT, DOMAIN, INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Platform setup."""
    return True


async def async_setup_entry(hass, entry):
    """Load the saved entities."""
    domain = entry.data[CONF_DOMAIN]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    session = hass.helpers.aiohttp_client.async_get_clientsession()

    coordinator = GoogleDomainsDataUpdateCoordinator(
        hass, session, domain, username, password
    )
    await coordinator.async_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    coordinator.async_add_listener(lambda: None)

    return True


class GoogleDomainsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage Google Domains dynamic DNS data."""

    def __init__(self, hass, session, domain, username, password):
        """Initialize global Google Domains data updater."""
        self.domain = domain
        self.username = username
        self.password = password
        self.timeout = DEFAULT_TIMEOUT

        self.session = session

        super().__init__(
            hass,
            _LOGGER,
            name=domain,
            update_interval=INTERVAL,
            update_method=self._async_update_data,
        )

    async def _async_update_data(self):
        """Update Google Domains."""

        url = f"https://{self.username}:{self.password}@domains.google.com/nic/update"

        params = {"hostname": self.domain}

        try:
            with async_timeout.timeout(self.timeout):
                resp = await self.session.get(url, params=params)
                body = await resp.text()

                if body.startswith("good") or body.startswith("nochg"):
                    return True

                _LOGGER.warning(
                    "Updating Google Domains failed: %s => %s", self.domain, body
                )

        except aiohttp.ClientError:
            _LOGGER.warning("Can't connect to Google Domains API")

        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout from Google Domains API for domain: %s", self.domain
            )

        return False
