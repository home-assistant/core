"""Support for Niko Home Control."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import nikohomecontrol
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    brightness_supported,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)
SCAN_INTERVAL = timedelta(seconds=30)

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Niko Home Control light platform."""
    host = config[CONF_HOST]

    try:
        nhc = nikohomecontrol.NikoHomeControl(
            {"ip": host, "port": 8000, "timeout": 20000}
        )
        niko_data = NikoHomeControlData(hass, nhc)
        await niko_data.async_update()
    except OSError as err:
        _LOGGER.error("Unable to access %s (%s)", host, err)
        raise PlatformNotReady from err

    async_add_entities(
        [NikoHomeControlLight(light, niko_data) for light in nhc.list_actions()], True
    )


class NikoHomeControlLight(LightEntity):
    """Representation of an Niko Light."""

    def __init__(self, light, data):
        """Set up the Niko Home Control light platform."""
        self._data = data
        self._light = light
        self._attr_unique_id = f"light-{light.id}"
        self._attr_name = light.name
        self._attr_is_on = light.is_on
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if light._state["type"] == 2:  # noqa: SLF001
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug("Turn on: %s", self.name)
        self._light.turn_on(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turn off: %s", self.name)
        self._light.turn_off()

    async def async_update(self) -> None:
        """Get the latest data from NikoHomeControl API."""
        await self._data.async_update()
        state = self._data.get_state(self._light.id)
        self._attr_is_on = state != 0
        if brightness_supported(self.supported_color_modes):
            self._attr_brightness = state * 2.55


class NikoHomeControlData:
    """The class for handling data retrieval."""

    def __init__(self, hass, nhc):
        """Set up Niko Home Control Data object."""
        self._nhc = nhc
        self.hass = hass
        self.available = True
        self.data = {}
        self._system_info = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the NikoHomeControl API."""
        _LOGGER.debug("Fetching async state in bulk")
        try:
            self.data = await self.hass.async_add_executor_job(
                self._nhc.list_actions_raw
            )
            self.available = True
        except OSError as ex:
            _LOGGER.error("Unable to retrieve data from Niko, %s", str(ex))
            self.available = False

    def get_state(self, aid):
        """Find and filter state based on action id."""
        for state in self.data:
            if state["id"] == aid:
                return state["value1"]
        _LOGGER.error("Failed to retrieve state off unknown light")
        return None
