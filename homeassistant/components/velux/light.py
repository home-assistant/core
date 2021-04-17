"""Support for Velux lights."""
from pyvlx import Intensity, LighteningDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.core import callback

from . import DATA_VELUX


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up light(s) for Velux platform."""
    entities = []
    for node in hass.data[DATA_VELUX].pyvlx.nodes:
        if isinstance(node, LighteningDevice):
            entities.append(VeluxLight(node))
    async_add_entities(entities)


class VeluxLight(LightEntity):
    """Representation of a Velux light."""

    def __init__(self, node):
        """Initialize the light."""
        self.node = node

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            self.async_write_ha_state()

        self.node.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

    @property
    def unique_id(self):
        """Return the unique ID of this cover."""
        return self.node.serial_number

    @property
    def name(self):
        """Return the name of the Velux device."""
        if not self.node.name:
            return "Light #" + str(self.node.node_id)
        return self.node.name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the current brightness."""
        brightness = int((100 - self.node.intensity.intensity_percent) * 255 / 100)
        return brightness

    @property
    def is_on(self):
        """Return true if light is on."""
        return not self.node.intensity.off and self.node.intensity.known

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        if ATTR_BRIGHTNESS in kwargs:
            intensityPercent = int(100 - kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            await self.node.set_intensity(
                Intensity(intensity_percent=intensityPercent), wait_for_completion=False
            )
        else:
            await self.node.turn_on(wait_for_completion=False)

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self.node.turn_off(wait_for_completion=False)
