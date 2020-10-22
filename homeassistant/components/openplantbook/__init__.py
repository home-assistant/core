"""The OpenPlantBook integration."""
import logging

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLANTBOOK_BASEURL

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the OpenPlantBook component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up OpenPlantBook from a config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN]["PLANTBOOK_TOKEN"] = entry.data.get("token")
    hass.data[DOMAIN]["API"] = OpenPlantBookApi(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data.pop(DOMAIN)

    return True


class OpenPlantBookApi:
    """Fetches data from the OpenPlantbook API."""

    def __init__(self, hass):
        """Initialize."""
        self.hass = hass

    async def get_plantbook_token(self, client_id, secret):
        """Get the token from the openplantbook API."""
        if not client_id or not secret:
            return False
        token = None
        url = f"{PLANTBOOK_BASEURL}/token/"
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": secret,
        }
        try:
            session = async_get_clientsession(self.hass)
            async with session.post(url, data=data) as result:
                token = await result.json()
                if token.get("access_token"):
                    _LOGGER.debug("Got token from %s", url)
                    return token

                raise InvalidAuth
        except Exception:  # pylint: disable=broad-except
            raise

    async def get_plantbook_data(self, species):
        """Get information about the plant from the openplantbook API."""
        if not self.hass.data[DOMAIN]["PLANTBOOK_TOKEN"]:
            _LOGGER.debug("No plantbook token")
            return
        url = f"{PLANTBOOK_BASEURL}/plant/detail/{species}"
        headers = {
            "Authorization": f"Bearer {self.hass.data[DOMAIN]['PLANTBOOK_TOKEN'].get('access_token')}"
        }
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, headers=headers) as result:
                _LOGGER.debug("Fetched data from %s", url)
                res = await result.json()
                return res
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unable to get plant from plantbook API: %s", str(e))
        return False


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
