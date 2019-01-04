"""
Support for the backlight of the Depict art frame.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.depict/
"""
import logging

from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.components.light import SUPPORT_BRIGHTNESS, Light
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from ..depict import ATTR_VALUE, DATA_DEPICT, SIGNAL_SET_CONTRAST

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['depict']

SUPPORTED_FEATURES = SUPPORT_BRIGHTNESS

DATA_CONTRAST = 'contrast'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a singlne Depict frame."""
    name = discovery_info[CONF_NAME]
    add_entities(
        [DepictLight(name, hass.data[DATA_DEPICT][name])],
        update_before_add=True)


class DepictLight(Light):
    """Represents a Depict art frame as a light."""

    def __init__(self, name, frame):
        """
        Constructor.

        :param name: name of the frame
        :param frame: depict-control Frame object
        """
        self._name = name
        self._frame = frame

    async def async_added_to_hass(self):
        """Register dispatcher handlers."""
        async_dispatcher_connect(self.hass, SIGNAL_SET_CONTRAST,
                                 self._handle_set_contrast)

    @property
    def name(self):
        """Return the name of the frame."""
        return self._name

    @property
    def is_on(self):
        """Return True if the frame is on."""
        return self._frame.is_on

    @property
    def brightness(self):
        """Return the current brightness of the frame's backlight."""
        return self._frame.brightness * 255 / 100

    async def _handle_set_contrast(self, data):
        entity_ids = data[ATTR_ENTITY_ID]
        if self.entity_id in entity_ids:
            await self._frame.set_contrast(data[ATTR_VALUE] * 100 / 255)

    @property
    def supported_features(self):
        """Return the features supported by the frame."""
        return SUPPORTED_FEATURES

    @property
    def device_state_attributes(self):
        """Return contrast setting in the state dictionary."""
        return {
            DATA_CONTRAST: self._frame.contrast * 255 / 100
        }

    async def async_turn_off(self, **kwargs):
        """Turn the frame off."""
        if self.is_on:
            await self._frame.sleep()

    async def async_turn_on(self, **kwargs):
        """Turn the frame on."""
        if not self.is_on:
            await self._frame.wakeup()

        if "brightness" in kwargs:
            await self._frame.set_brightness(kwargs["brightness"] * 100 / 255)

    async def async_update(self):
        """Refresh the state of the frame."""
        await self._frame.update()
