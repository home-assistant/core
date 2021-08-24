"""Support for Gardena Smart System devices."""
import logging

from gardena.smart_system import SmartSystem
from gardena.exceptions.authentication_exception import AuthenticationException

from oauthlib.oauth2.rfc6749.errors import (
    AccessDeniedError,
    InvalidClientError,
    MissingTokenError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from .const import(
    DOMAIN,
    GARDENA_LOCATION,
    GARDENA_SYSTEM,
)


_LOGGER = logging.getLogger(__name__)

PLATFORMS = ("vacuum", "sensor", "switch", "binary_sensor")


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Gardena Smart System integration."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("Setting up Gardena Smart System component")

    gardena_system = GardenaSmartSystem(
        hass,
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        client_id=entry.data[CONF_CLIENT_ID])

    try:
        await hass.async_add_executor_job(gardena_system.start)
    except AccessDeniedError as ex:
        _LOGGER.error("Got Access Denied Error when setting up Gardena Smart System: %s", ex)
        return False
    except InvalidClientError as ex:
        _LOGGER.error("Got Invalid Client Error when setting up Gardena Smart System: %s", ex)
        return False
    except MissingTokenError as ex:
        _LOGGER.error("Got Missing Token Error when setting up Gardena Smart System: %s", ex)
        return False

    hass.data[DOMAIN][GARDENA_SYSTEM] = gardena_system

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, lambda event: gardena_system.stop())

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component))

    _LOGGER.debug("Gardena Smart System component setup finished")
    return True


class GardenaSmartSystem:
    """A Gardena Smart System wrapper class."""

    def __init__(self, hass, *, email, password, client_id, smart_system=SmartSystem):
        """Initialize the Gardena Smart System."""
        self._hass = hass
        self.smart_system = smart_system(
            email=email,
            password=password,
            client_id=client_id)

    def start(self):
        _LOGGER.debug("Starting GardenaSmartSystem")
        try:
            self.smart_system.authenticate()
            self.smart_system.update_locations()

            if len(self.smart_system.locations) < 1:
                _LOGGER.error("No locations found")
                raise Exception("No locations found")

            # currently gardena supports only one location and gateway, so we can take the first
            location = list(self.smart_system.locations.values())[0]
            _LOGGER.debug(f"Using location: {location.name} ({location.id})")
            self.smart_system.update_devices(location)
            self._hass.data[DOMAIN][GARDENA_LOCATION] = location
            _LOGGER.debug("Starting GardenaSmartSystem websocket")
            self.smart_system.start_ws(self._hass.data[DOMAIN][GARDENA_LOCATION])
        except AuthenticationException as ex:
            _LOGGER.error(f"Authentication failed : {ex.message}. You may need to dcheck your token or create a new app in the gardena api and use the new token.")

    def stop(self):
        _LOGGER.debug("Stopping GardenaSmartSystem")
        self.smart_system.quit()
