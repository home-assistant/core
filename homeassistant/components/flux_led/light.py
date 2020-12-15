"""Support for FluxLED/MagicHome lights."""

from datetime import timedelta
import logging
import random
import time

from flux_led import WifiLedBulb

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import ATTR_NAME, CONF_HOST, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import homeassistant.util.color as color_util

from . import FluxLEDListUpdateCoordinator
from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    BULB_COORDINATOR,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SPEED,
    DOMAIN,
    SIGNAL_ADD_DEVICE,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLUX_LED = SUPPORT_BRIGHTNESS | SUPPORT_EFFECT | SUPPORT_COLOR

MODE_RGB = "rgb"
MODE_RGBW = "rgbw"

# This mode enables white value to be controlled by brightness.
# RGB value is ignored when this mode is specified.
MODE_WHITE = "w"

# List of supported effects which aren't already declared in LIGHT
EFFECT_RED_FADE = "red_fade"
EFFECT_GREEN_FADE = "green_fade"
EFFECT_BLUE_FADE = "blue_fade"
EFFECT_YELLOW_FADE = "yellow_fade"
EFFECT_CYAN_FADE = "cyan_fade"
EFFECT_PURPLE_FADE = "purple_fade"
EFFECT_WHITE_FADE = "white_fade"
EFFECT_RED_GREEN_CROSS_FADE = "rg_cross_fade"
EFFECT_RED_BLUE_CROSS_FADE = "rb_cross_fade"
EFFECT_GREEN_BLUE_CROSS_FADE = "gb_cross_fade"
EFFECT_COLORSTROBE = "colorstrobe"
EFFECT_RED_STROBE = "red_strobe"
EFFECT_GREEN_STROBE = "green_strobe"
EFFECT_BLUE_STROBE = "blue_strobe"
EFFECT_YELLOW_STROBE = "yellow_strobe"
EFFECT_CYAN_STROBE = "cyan_strobe"
EFFECT_PURPLE_STROBE = "purple_strobe"
EFFECT_WHITE_STROBE = "white_strobe"
EFFECT_COLORJUMP = "colorjump"
EFFECT_CUSTOM = "custom"

EFFECT_MAP = {
    EFFECT_COLORLOOP: 0x25,
    EFFECT_RED_FADE: 0x26,
    EFFECT_GREEN_FADE: 0x27,
    EFFECT_BLUE_FADE: 0x28,
    EFFECT_YELLOW_FADE: 0x29,
    EFFECT_CYAN_FADE: 0x2A,
    EFFECT_PURPLE_FADE: 0x2B,
    EFFECT_WHITE_FADE: 0x2C,
    EFFECT_RED_GREEN_CROSS_FADE: 0x2D,
    EFFECT_RED_BLUE_CROSS_FADE: 0x2E,
    EFFECT_GREEN_BLUE_CROSS_FADE: 0x2F,
    EFFECT_COLORSTROBE: 0x30,
    EFFECT_RED_STROBE: 0x31,
    EFFECT_GREEN_STROBE: 0x32,
    EFFECT_BLUE_STROBE: 0x33,
    EFFECT_YELLOW_STROBE: 0x34,
    EFFECT_CYAN_STROBE: 0x35,
    EFFECT_PURPLE_STROBE: 0x36,
    EFFECT_WHITE_STROBE: 0x37,
    EFFECT_COLORJUMP: 0x38,
}
EFFECT_CUSTOM_CODE = 0x60

TRANSITION_GRADUAL = "gradual"
TRANSITION_JUMP = "jump"
TRANSITION_STROBE = "strobe"

FLUX_EFFECT_LIST = sorted(list(EFFECT_MAP)) + [EFFECT_RANDOM]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Flux lights."""
    config_type = hass.data[DOMAIN][entry.entry_id][CONF_TYPE]
    lights = []

    async def add_light(
        bulb_name: str,
        unique_id: str,
        ip_address: str,
        config_type: str,
        bulb: dict,
        bulb_coordinator: FluxLEDListUpdateCoordinator = None,
    ):
        """Structure the light to be added as an entity."""
        coordinator = FluxLEDCoordinator(
            hass=hass,
            name=bulb_name,
            update_interval=DEFAULT_SCAN_INTERVAL,
            ip_address=ip_address,
            config_type=config_type,
            scan_coordinator=bulb_coordinator,
        )

        await coordinator.async_refresh()

        return FluxLight(
            coordinator=coordinator,
            unique_id=unique_id,
            bulb_name=bulb_name,
            config_type=config_type,
            device=bulb,
        )

    if config_type == "auto":
        bulb_coordinator = hass.data[DOMAIN][entry.entry_id][BULB_COORDINATOR]

        for bulb_id, bulb in bulb_coordinator.data.items():
            lights.append(
                await add_light(
                    bulb_name=bulb_id,
                    unique_id=bulb_id,
                    ip_address=bulb["ipaddr"],
                    config_type="auto",
                    bulb=bulb,
                    bulb_coordinator=bulb_coordinator,
                )
            )

    else:
        bulb = {
            "ipaddr": hass.data[DOMAIN][entry.entry_id][CONF_HOST],
            "id": hass.data[DOMAIN][entry.entry_id][CONF_HOST].replace(".", "_"),
            "model": "Manual Configured Device",
            "active": True,
        }

        lights.append(
            await add_light(
                bulb_name=hass.data[DOMAIN][entry.entry_id][CONF_NAME],
                unique_id=bulb["ipaddr"].replace(".", "_"),
                ip_address=bulb["ipaddr"],
                config_type="manual",
                bulb=bulb,
            )
        )

    async_add_entities(lights)

    async def async_new_lights(bulb: dict):
        """Add a new bulb when it is connected to the network for auto configured."""
        coordinator = FluxLEDCoordinator(
            hass=hass,
            name=bulb["id"],
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_type="auto",
            ip_address=bulb["ipaddr"],
            scan_coordinator=bulb_coordinator,
        )

        await coordinator.async_refresh()

        async_add_entities(
            [
                FluxLight(
                    coordinator=coordinator,
                    unique_id=bulb["id"],
                    bulb_name=bulb["id"],
                    config_type="auto",
                    device=bulb,
                )
            ]
        )

    async_dispatcher_connect(hass, SIGNAL_ADD_DEVICE, async_new_lights)


class FluxLEDCoordinator(DataUpdateCoordinator):
    """Update Coordinator for a specific light entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        update_interval: int,
        ip_address: str,
        config_type: str,
        scan_coordinator: FluxLEDListUpdateCoordinator = None,
    ):
        """Initialize the update coordinator."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=timedelta(milliseconds=update_interval),
        )

        self._ip_address = ip_address
        self._type = config_type
        self._name = name
        self.scan_coordinator = scan_coordinator

        self.light = WifiLedBulb(self._ip_address)

    async def update_ip(self, ip_address: str):
        """Update a change to the light IP address."""
        self._ip_address = ip_address
        self.light = None
        self.light = WifiLedBulb(self._ip_address)

    async def _async_update_data(self):
        """Fetch the data from this light bulb."""

        if self._type == "auto":
            current_ip = self.scan_coordinator.data[self._name]["ipaddr"]
            if current_ip != self._ip_address:
                await self.update_ip(current_ip)

        self.light.update_state()


class FluxLight(CoordinatorEntity, LightEntity):
    """Represents a Flux Light entity."""

    def __init__(
        self,
        coordinator: FluxLEDCoordinator,
        unique_id: str,
        bulb_name: str,
        config_type: str,
        device: dict,
    ):
        """Initialize the Flux light entity."""
        super().__init__(coordinator=coordinator)

        self._name = bulb_name
        self._unique_id = unique_id
        self._config_type = config_type
        self._icon = "mdi:lightbulb"
        self._attrs = {}
        self._last_update = 0
        self._state = None
        self._brightness = None
        self._hs_color = None
        self._bulb = coordinator.light
        self._last_brightness = 255
        self._last_hs_color = color_util.color_RGB_to_hs(255, 255, 255)
        self._model = device["model"]
        self._ip_address = device["ipaddr"]

        if self._bulb.mode == "ww":
            self._mode = MODE_WHITE
        elif self._bulb.rgbwcapable:
            self._mode = MODE_RGBW
        else:
            self._mode = MODE_RGB

    @property
    def unique_id(self):
        """Return the unique ID of the light."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def available(self):
        """Return if the light is available."""
        available = True
        if self._config_type == "auto":
            available = self.coordinator.scan_coordinator.data[self._unique_id][
                "active"
            ]

        return available

    @property
    def is_on(self):
        """Return true if the light is on."""
        state = self._bulb.isOn() and self.brightness > 0
        if time.time() - self._last_update < 1:
            state = self._state

        return state

    @property
    def brightness(self):
        """Return the brightness of the light."""
        brightness = self._brightness if self._brightness else 0
        if time.time() - self._last_update < 1:
            if self._mode == MODE_WHITE:
                brightness = self.white_value

            brightness = self._bulb.brightness
            self._last_brightness = brightness

        return brightness

    @property
    def hs_color(self):
        """Return the color property."""
        hs_color = self._hs_color
        if time.time() - self._last_update < 1:
            hs_color = color_util.color_RGB_to_hs(*self._bulb.getRgb())
            self._last_hs_color = hs_color
        return hs_color

    @property
    def white_value(self):
        """Return the white value of this light."""
        return self._bulb.getRgbw()[3]

    @property
    def supported_features(self):
        """Return the supported features for this light."""
        if self._mode == MODE_RGBW:
            return SUPPORT_FLUX_LED | SUPPORT_WHITE_VALUE

        return SUPPORT_FLUX_LED

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return FLUX_EFFECT_LIST

    @property
    def effect(self):
        """Return the current effect."""
        current_mode = self._bulb.raw_state[3]

        for effect, code in EFFECT_MAP.items():
            if current_mode == code:
                return effect

        return None

    @property
    def device_state_attributes(self):
        """Return the attributes."""
        if self._config_type == "auto":
            self._attrs["ip_address"] = self.coordinator.scan_coordinator.data[
                self._unique_id
            ]["ipaddr"]
        else:
            self._attrs["ip_address"] = self._ip_address

        return self._attrs

    @property
    def device_info(self):
        """Return the device information."""
        device_name = "FluxLED/Magic Home"
        device_model = self._model

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._unique_id)},
            ATTR_NAME: self._name,
            ATTR_MANUFACTURER: device_name,
            ATTR_MODEL: device_model,
        }

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""

        rgb = None
        hs_color = kwargs.get(ATTR_HS_COLOR)

        if hs_color:
            rgb = color_util.color_hs_to_RGB(*hs_color)

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        white = kwargs.get(ATTR_WHITE_VALUE)

        if effect == EFFECT_RANDOM:
            color_red = random.randint(0, 255)
            color_green = random.randint(0, 255)
            color_blue = random.randint(0, 255)

            self._bulb.setRgbw(
                r=color_red,
                g=color_green,
                b=color_blue,
            )

            self._hs_color = color_util.color_RGB_to_hs(
                color_red,
                color_green,
                color_blue,
            )
            self._last_update = time.time()

            return

        if effect in EFFECT_MAP:
            self._bulb.setPresetPattern(EFFECT_MAP[effect], DEFAULT_SPEED)

        if not brightness:
            brightness = self._last_brightness

        self._last_brightness = brightness
        self._brightness = brightness

        if not rgb:
            rgb = color_util.color_hs_to_RGB(*self._last_hs_color)

        self._hs_color = color_util.color_RGB_to_hs(*tuple(rgb))

        if not white and self._mode == MODE_RGBW:
            white = self.white_value

        if self._mode == MODE_WHITE:
            self._bulb.setRgbw(0, 0, 0, w=brightness)

        elif self._mode == MODE_RGBW:
            self._bulb.setRgbw(*tuple(rgb), w=white, brightness=brightness)

        else:
            self._bulb.setRgb(*tuple(rgb), brightness=brightness)

        self._state = True
        self._last_update = time.time()

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""

        rgb = self._bulb.getRgb()
        self._last_brightness = self.brightness
        self._last_hs_color = self.hs_color

        if self._mode == MODE_WHITE:
            self._bulb.setRgbw(0, 0, 0, w=0)

        elif self._mode == MODE_RGBW:
            self._bulb.setRgbw(*tuple(rgb), w=0, brightness=0)

        else:
            self._bulb.setRgb(*tuple(rgb), brightness=0)

        self._state = False
        self._last_update = time.time()
