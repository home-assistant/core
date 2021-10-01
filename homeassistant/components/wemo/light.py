"""Support for Belkin WeMo lights."""
import asyncio
import logging

from pywemo.ouimeaux_device import bridge

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.color as color_util

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoEntity
from .wemo_device import DeviceCoordinator

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEMO = (
    SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR | SUPPORT_TRANSITION
)

# The WEMO_ constants below come from pywemo itself
WEMO_OFF = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WeMo lights."""

    async def _discovered_wemo(coordinator: DeviceCoordinator):
        """Handle a discovered Wemo device."""
        if isinstance(coordinator.wemo, bridge.Bridge):
            async_setup_bridge(hass, config_entry, async_add_entities, coordinator)
        else:
            async_add_entities([WemoDimmer(coordinator)])

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.light", _discovered_wemo)

    await asyncio.gather(
        *(
            _discovered_wemo(coordinator)
            for coordinator in hass.data[WEMO_DOMAIN]["pending"].pop("light")
        )
    )


@callback
def async_setup_bridge(hass, config_entry, async_add_entities, coordinator):
    """Set up a WeMo link."""
    known_light_ids = set()

    @callback
    def async_update_lights():
        """Check to see if the bridge has any new lights."""
        new_lights = []

        for light_id, light in coordinator.wemo.Lights.items():
            if light_id not in known_light_ids:
                known_light_ids.add(light_id)
                new_lights.append(WemoLight(coordinator, light))

        if new_lights:
            async_add_entities(new_lights)

    async_update_lights()
    config_entry.async_on_unload(coordinator.async_add_listener(async_update_lights))


class WemoLight(WemoEntity, LightEntity):
    """Representation of a WeMo light."""

    def __init__(self, coordinator: DeviceCoordinator, light: bridge.Light) -> None:
        """Initialize the WeMo light."""
        super().__init__(coordinator)
        self.light = light
        self._unique_id = self.light.uniqueID
        self._model_name = type(self.light).__name__

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self.light.name

    @property
    def available(self) -> bool:
        """Return true if the device is available."""
        return super().available and self.light.state.get("available")

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self.light.uniqueID

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self.name,
            "connections": {(CONNECTION_ZIGBEE, self._unique_id)},
            "identifiers": {(WEMO_DOMAIN, self._unique_id)},
            "model": self._model_name,
            "manufacturer": "Belkin",
        }

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.light.state.get("level", 255)

    @property
    def hs_color(self):
        """Return the hs color values of this light."""
        xy_color = self.light.state.get("color_xy")
        if xy_color:
            return color_util.color_xy_to_hs(*xy_color)
        return None

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds."""
        return self.light.state.get("temperature_mireds")

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.light.state.get("onoff") != WEMO_OFF

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_WEMO

    def turn_on(self, **kwargs):
        """Turn the light on."""
        xy_color = None

        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        transition_time = int(kwargs.get(ATTR_TRANSITION, 0))

        if hs_color is not None:
            xy_color = color_util.color_hs_to_xy(*hs_color)

        turn_on_kwargs = {
            "level": brightness,
            "transition": transition_time,
            "force_update": False,
        }

        with self._wemo_exception_handler("turn on"):
            if xy_color is not None:
                self.light.set_color(xy_color, transition=transition_time)

            if color_temp is not None:
                self.light.set_temperature(
                    mireds=color_temp, transition=transition_time
                )

            self.light.turn_on(**turn_on_kwargs)

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        transition_time = int(kwargs.get(ATTR_TRANSITION, 0))

        with self._wemo_exception_handler("turn off"):
            self.light.turn_off(transition=transition_time)

        self.schedule_update_ha_state()


class WemoDimmer(WemoEntity, LightEntity):
    """Representation of a WeMo dimmer."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of this light between 1 and 100."""
        wemo_brightness = int(self.wemo.get_brightness())
        return int((wemo_brightness * 255) / 100)

    @property
    def is_on(self) -> bool:
        """Return true if the state is on."""
        return self.wemo.get_state()

    def turn_on(self, **kwargs):
        """Turn the dimmer on."""
        # Wemo dimmer switches use a range of [0, 100] to control
        # brightness. Level 255 might mean to set it to previous value
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int((brightness / 255) * 100)
            with self._wemo_exception_handler("set brightness"):
                self.wemo.set_brightness(brightness)
        else:
            with self._wemo_exception_handler("turn on"):
                self.wemo.on()

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the dimmer off."""
        with self._wemo_exception_handler("turn off"):
            self.wemo.off()

        self.schedule_update_ha_state()
