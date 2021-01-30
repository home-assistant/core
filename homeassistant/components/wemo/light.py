"""Support for Belkin WeMo lights."""
import asyncio
from datetime import timedelta
import logging

from pywemo.ouimeaux_device.api.service import ActionException

from homeassistant import util
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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.color as color_util

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoEntity, WemoSubscriptionEntity

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

_LOGGER = logging.getLogger(__name__)

SUPPORT_WEMO = (
    SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR | SUPPORT_TRANSITION
)

# The WEMO_ constants below come from pywemo itself
WEMO_ON = 1
WEMO_OFF = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WeMo lights."""

    async def _discovered_wemo(device):
        """Handle a discovered Wemo device."""
        if device.model_name == "Dimmer":
            async_add_entities([WemoDimmer(device)])
        else:
            await hass.async_add_executor_job(
                setup_bridge, hass, device, async_add_entities
            )

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.light", _discovered_wemo)

    await asyncio.gather(
        *[
            _discovered_wemo(device)
            for device in hass.data[WEMO_DOMAIN]["pending"].pop("light")
        ]
    )


def setup_bridge(hass, bridge, async_add_entities):
    """Set up a WeMo link."""
    lights = {}

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_lights():
        """Update the WeMo led objects with latest info from the bridge."""
        bridge.bridge_update()

        new_lights = []

        for light_id, device in bridge.Lights.items():
            if light_id not in lights:
                lights[light_id] = WemoLight(device, update_lights)
                new_lights.append(lights[light_id])

        if new_lights:
            hass.add_job(async_add_entities, new_lights)

    update_lights()


class WemoLight(WemoEntity, LightEntity):
    """Representation of a WeMo light."""

    def __init__(self, device, update_lights):
        """Initialize the WeMo light."""
        super().__init__(device)
        self._update_lights = update_lights
        self._brightness = None
        self._hs_color = None
        self._color_temp = None
        self._is_on = None
        self._unique_id = self.wemo.uniqueID
        self._model_name = type(self.wemo).__name__

    async def async_added_to_hass(self):
        """Wemo light added to Home Assistant."""
        # Define inside async context so we know our event loop
        self._update_lock = asyncio.Lock()

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self.wemo.uniqueID

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self.name,
            "identifiers": {(WEMO_DOMAIN, self._unique_id)},
            "model": self._model_name,
            "manufacturer": "Belkin",
        }

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hs color values of this light."""
        return self._hs_color

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds."""
        return self._color_temp

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._is_on

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

        try:
            if xy_color is not None:
                self.wemo.set_color(xy_color, transition=transition_time)

            if color_temp is not None:
                self.wemo.set_temperature(mireds=color_temp, transition=transition_time)

            if self.wemo.turn_on(**turn_on_kwargs):
                self._state["onoff"] = WEMO_ON
        except ActionException as err:
            _LOGGER.warning("Error while turning on device %s (%s)", self.name, err)
            self._available = False

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        transition_time = int(kwargs.get(ATTR_TRANSITION, 0))

        try:
            if self.wemo.turn_off(transition=transition_time):
                self._state["onoff"] = WEMO_OFF
        except ActionException as err:
            _LOGGER.warning("Error while turning off device %s (%s)", self.name, err)
            self._available = False

        self.schedule_update_ha_state()

    def _update(self, force_update=True):
        """Synchronize state with bridge."""
        try:
            self._update_lights(no_throttle=force_update)
            self._state = self.wemo.state
        except (AttributeError, ActionException) as err:
            _LOGGER.warning("Could not update status for %s (%s)", self.name, err)
            self._available = False
            self.wemo.bridge.reconnect_with_device()
        else:
            self._is_on = self._state.get("onoff") != WEMO_OFF
            self._brightness = self._state.get("level", 255)
            self._color_temp = self._state.get("temperature_mireds")
            self._available = True

            xy_color = self._state.get("color_xy")

            if xy_color:
                self._hs_color = color_util.color_xy_to_hs(*xy_color)
            else:
                self._hs_color = None


class WemoDimmer(WemoSubscriptionEntity, LightEntity):
    """Representation of a WeMo dimmer."""

    def __init__(self, device):
        """Initialize the WeMo dimmer."""
        super().__init__(device)
        self._brightness = None

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of this light between 1 and 100."""
        return self._brightness

    def _update(self, force_update=True):
        """Update the device state."""
        try:
            self._state = self.wemo.get_state(force_update)

            wemobrightness = int(self.wemo.get_brightness(force_update))
            self._brightness = int((wemobrightness * 255) / 100)

            if not self._available:
                _LOGGER.info("Reconnected to %s", self.name)
                self._available = True
        except (AttributeError, ActionException) as err:
            _LOGGER.warning("Could not update status for %s (%s)", self.name, err)
            self._available = False
            self.wemo.reconnect_with_device()

    def turn_on(self, **kwargs):
        """Turn the dimmer on."""
        # Wemo dimmer switches use a range of [0, 100] to control
        # brightness. Level 255 might mean to set it to previous value
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = int((brightness / 255) * 100)
        else:
            brightness = 255

        try:
            if self.wemo.on():
                self._state = WEMO_ON

            self.wemo.set_brightness(brightness)
        except ActionException as err:
            _LOGGER.warning("Error while turning on device %s (%s)", self.name, err)
            self._available = False

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the dimmer off."""
        try:
            if self.wemo.off():
                self._state = WEMO_OFF
        except ActionException as err:
            _LOGGER.warning("Error while turning on device %s (%s)", self.name, err)
            self._available = False

        self.schedule_update_ha_state()
