"""Support for a ScreenLogic light 'circuit' switch."""
import logging
from math import sqrt

from screenlogicpy.const import CIRCUIT_FUNCTION, DATA as SL_DATA, GENERIC_CIRCUIT_NAMES

from homeassistant.components.light import ATTR_RGB_COLOR, COLOR_MODE_RGB, LightEntity
from homeassistant.exceptions import HomeAssistantError

from . import ScreenLogicCircuitEntity
from .const import DOMAIN, LIGHT_CIRCUIT_FUNCTIONS, SUPPORTED_COLOR_MODES

_LOGGER = logging.getLogger(__name__)


SUPPORTED_COLORS = {
    (255, 0, 0): SUPPORTED_COLOR_MODES["red"],
    (0, 255, 0): SUPPORTED_COLOR_MODES["green"],
    (0, 0, 255): SUPPORTED_COLOR_MODES["blue"],
    (255, 0, 255): SUPPORTED_COLOR_MODES["magenta"],
    (255, 255, 255): SUPPORTED_COLOR_MODES["white"],
}


def find_closest_color(rgb):
    """Find the cloest color num the device supports."""
    return min(
        (
            sqrt(
                abs(rgb[0] - supported_rgb[0]) ** 2
                + abs(rgb[1] - supported_rgb[1]) ** 2
                + abs(rgb[2] - supported_rgb[2]) ** 2
            ),
            supported_rgb,
        )
        for supported_rgb in SUPPORTED_COLORS
    )[1]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for circuit_num, circuit in coordinator.data[SL_DATA.KEY_CIRCUITS].items():
        if circuit["function"] not in LIGHT_CIRCUIT_FUNCTIONS:
            continue
        if circuit["function"] == CIRCUIT_FUNCTION.INTELLIBRITE:
            cls = ScreenLogicIntelliBriteLight
        else:
            cls = ScreenLogicLight
        entities.append(
            cls(coordinator, circuit_num, circuit["name"] not in GENERIC_CIRCUIT_NAMES)
        )
    async_add_entities(entities)


class ScreenLogicLight(ScreenLogicCircuitEntity, LightEntity):
    """Class to represent a ScreenLogic Light."""


class ScreenLogicIntelliBriteLight(ScreenLogicLight):
    """Class to represent a ScreenLogic Light."""

    def __init__(self, coordinator, data_key, enabled=True):
        """Initialize of the entity."""
        super().__init__(coordinator, data_key, enabled)
        self._attr_color_mode = COLOR_MODE_RGB
        self._attr_supported_color_modes = [COLOR_MODE_RGB]
        self._attr_brightness = 255

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the lights to the cloest color."""
        await super().async_turn_on(**kwargs)
        if (rgb := kwargs.get(ATTR_RGB_COLOR)) is None:
            return
        actual_rgb = find_closest_color(rgb)
        color_num = SUPPORTED_COLORS[actual_rgb]
        if not await self.coordinator.gateway.async_set_color_lights(color_num):
            raise HomeAssistantError(f"Failed to set color lights to {rgb}")
        self._attr_rgb_color = actual_rgb
        self.async_write_ha_state()
        # Debounced refresh to catch any secondary
        # changes in the device
        await self.coordinator.async_request_refresh()
