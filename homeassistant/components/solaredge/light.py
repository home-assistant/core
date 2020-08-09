"""Support for SolarEdge HA API."""
import logging

from requests.exceptions import ConnectTimeout, HTTPError
import solaredgeha

from homeassistant.components.light import LightEntity
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.util import Throttle

from .const import CONF_SITE_ID, LIGHT_UPDATE_DELAY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add an solarEdge entry."""

    # Add the lights to hass
    api = solaredgeha.SolaredgeHa(
        entry.data[CONF_SITE_ID], entry.data[CONF_ACCESS_TOKEN]
    )

    # Check if api can be reached and site is active
    try:
        response = await hass.async_add_executor_job(api.get_devices)
        if response["status"] != "PASSED":
            _LOGGER.error("SolarEdge HA site is not active")
            return
        _LOGGER.debug("Credentials correct and site is active")
    except (ConnectTimeout, HTTPError):
        _LOGGER.error("Could not retrieve details from SolarEdge API")
        return

    service = SolarEdgeLightService(entry.title, api, async_add_entities)
    await hass.async_add_executor_job(service.update)


class SolarEdgeLightService:
    """Get and update the HA device data."""

    def __init__(self, platform_name, api, async_add_entities):
        """Initialize the data object."""
        self.platform_name = platform_name
        self.api = api
        self.async_add_entities = async_add_entities

        self.devices = {}

    @Throttle(LIGHT_UPDATE_DELAY)
    def update(self):
        """Update the devices from SolarEdge HA API."""

        try:
            response = self.api.get_devices()
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, skipping update")
            return

        for device in response["devices"]:
            if device["type"] == "ON_OFF":
                key = device["reporterId"]
                if key not in self.devices:
                    _LOGGER.debug("SolarEdge HA adding new light %s", key)
                    self.devices[key] = device
                    self.async_add_entities(
                        [SolarEdgeLight(self.platform_name, key, self)]
                    )
                else:
                    _LOGGER.debug("SolarEdge HA updating light %s", key)
                    self.devices[key] = device


class SolarEdgeLight(LightEntity):
    """Representation of a SolarEdge HA light."""

    def __init__(self, platform_name, light_key, light_service):
        """Initialize the light."""
        self._platform_name = platform_name
        self._light_key = light_key
        self._light_service = light_service
        self._state = self._light_service.devices[self._light_key]

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._light_key

    @property
    def name(self):
        """Return the display name of this light."""
        return self._state["name"]

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state["status"]["level"] > 0

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        self._light_service.api.activate_device(self._light_key, 100)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light_service.api.activate_device(self._light_key, 0)

    def update(self):
        """Fetch new state data for this light."""
        self._light_service.update()
        self._state = self._light_service.devices[self._light_key]
