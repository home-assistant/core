"""Support for ISY994 lights."""
from typing import Callable, Dict

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.light import (
    DOMAIN as LIGHT,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from . import ISY994_NODES
from .const import _LOGGER
from .entity import ISYNodeEntity

ATTR_LAST_BRIGHTNESS = "last_brightness"


def setup_platform(
    hass, config: ConfigType, add_entities: Callable[[list], None], discovery_info=None
):
    """Set up the ISY994 light platform."""
    devices = []
    for node in hass.data[ISY994_NODES][LIGHT]:
        devices.append(ISYLightEntity(node))

    add_entities(devices)


class ISYLightEntity(ISYNodeEntity, LightEntity, RestoreEntity):
    """Representation of an ISY994 light device."""

    def __init__(self, node) -> None:
        """Initialize the ISY994 light device."""
        super().__init__(node)
        self._last_brightness = None

    @property
    def is_on(self) -> bool:
        """Get whether the ISY994 light is on."""
        if self.value == ISY_VALUE_UNKNOWN:
            return False
        return int(self.value) != 0

    @property
    def brightness(self) -> float:
        """Get the brightness of the ISY994 light."""
        return STATE_UNKNOWN if self.value == ISY_VALUE_UNKNOWN else int(self.value)

    def turn_off(self, **kwargs) -> None:
        """Send the turn off command to the ISY994 light device."""
        self._last_brightness = self.brightness
        if not self._node.turn_off():
            _LOGGER.debug("Unable to turn off light")

    def on_update(self, event: object) -> None:
        """Save brightness in the update event from the ISY994 Node."""
        if self.value not in (0, ISY_VALUE_UNKNOWN):
            self._last_brightness = self.value
        super().on_update(event)

    # pylint: disable=arguments-differ
    def turn_on(self, brightness=None, **kwargs) -> None:
        """Send the turn on command to the ISY994 light device."""
        if brightness is None and self._last_brightness:
            brightness = self._last_brightness
        if not self._node.turn_on(val=brightness):
            _LOGGER.debug("Unable to turn on light")

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def device_state_attributes(self) -> Dict:
        """Return the light attributes."""
        attribs = super().device_state_attributes
        attribs[ATTR_LAST_BRIGHTNESS] = self._last_brightness
        return attribs

    async def async_added_to_hass(self) -> None:
        """Restore last_brightness on restart."""
        await super().async_added_to_hass()

        self._last_brightness = self.brightness or 255
        last_state = await self.async_get_last_state()
        if not last_state:
            return

        if (
            ATTR_LAST_BRIGHTNESS in last_state.attributes
            and last_state.attributes[ATTR_LAST_BRIGHTNESS]
        ):
            self._last_brightness = last_state.attributes[ATTR_LAST_BRIGHTNESS]
