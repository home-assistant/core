"""Contec light entity."""

import logging

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Awesome Light platform."""
    # Assign configuration variables.
    # The configuration check takes care they are present.
    # host = config[CONF_HOST]
    # username = config[CONF_USERNAME]
    # password = config.get(CONF_PASSWORD)

    # Setup connection with devices/cloud
    # hub = awesomelights.Hub(host, username, password)

    # Verify that passed in configuration works
    # if not hub.is_valid_login():
    #    _LOGGER.error("Could not connect to AwesomeLight hub")
    #    return

    # Add devices
    # add_entities(AwesomeLight(light) for light in hub.lights())
    _LOGGER.info("Hello world")
    light1 = TestLight("contec_1", "Light1")
    light2 = TestLight("contec_2", "Light2")
    async_add_entities([light1, light2])


class TestLight(LightEntity):
    """Representation of an Awesome Light."""

    _id: str
    _state: bool
    _name: str

    def __init__(self, id: str, name: str):
        """Initialize an AwesomeLight."""
        self._id = id
        self._name = name
        self._state = False
        self._brightness = None

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def brightness(self):
        """
        Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._id

    def turn_on(self, **kwargs) -> None:
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
        self._state = True

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._state = False

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        # Nothing to do.
        pass
