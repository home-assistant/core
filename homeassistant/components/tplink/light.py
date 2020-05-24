"""Support for TPLink lights."""
from datetime import timedelta
import logging

from kasa import SmartBulb, SmartDeviceException

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)

from . import CONF_LIGHT, DOMAIN as TPLINK_DOMAIN
from .common import async_add_entities_retry

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_POWER_W = "current_power_w"
ATTR_DAILY_ENERGY_KWH = "daily_energy_kwh"
ATTR_MONTHLY_ENERGY_KWH = "monthly_energy_kwh"


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    """Set up switches."""
    await async_add_entities_retry(
        hass, async_add_entities, hass.data[TPLINK_DOMAIN][CONF_LIGHT], add_entity
    )

    return True


async def add_entity(device: SmartBulb, async_add_entities):
    """Check if device is online and add the entity."""
    # Attempt to get the sysinfo. If it fails, it will raise an
    # exception that is caught by async_add_entities_retry which
    # will try again later.
    await device.update()

    async_add_entities([TPLinkSmartBulb(device)], update_before_add=True)


def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return round((byt * 100.0) / 255.0)


def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return round((percent * 255.0) / 100.0)


class TPLinkSmartBulb(LightEntity):
    """Representation of a TPLink Smart Bulb."""

    def __init__(self, smartbulb: SmartBulb) -> None:
        """Initialize the bulb."""
        self.smartbulb = smartbulb
        self._min_mireds = None
        self._max_mireds = None
        self._is_available = True
        self._supported_features = None
        self._device_state_attributes = {}

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.smartbulb.mac

    @property
    def name(self):
        """Return the name of the Smart Bulb."""
        return self.smartbulb.alias

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self.smartbulb.alias,
            "model": self.smartbulb.model,
            "manufacturer": "TP-Link",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.smartbulb.mac)},
            "sw_version": self.smartbulb.sys_info["sw_ver"],
        }

    @property
    def available(self) -> bool:
        """Return if bulb is available."""
        return self._is_available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._device_state_attributes

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])

        try:
            if brightness is not None and self.smartbulb.is_dimmable:
                await self.smartbulb.set_brightness(
                    brightness_to_percentage(brightness)
                )
            if ATTR_COLOR_TEMP in kwargs and self.smartbulb.is_variable_color_temp:
                color_temp = int(mired_to_kelvin(int(kwargs[ATTR_COLOR_TEMP])))
                await self.smartbulb.set_color_temp(color_temp)
            if ATTR_HS_COLOR in kwargs and self.smartbulb.is_color:
                hue, sat = kwargs[ATTR_HS_COLOR]
                if brightness is None:
                    brightness = self.brightness
                # TODO: allow floats in upstream for hue&sat?
                await self.smartbulb.set_hsv(
                    int(hue), int(sat), brightness_to_percentage(brightness)
                )

            await self.smartbulb.turn_on()
            self._is_available = True
            return
        except (SmartDeviceException, OSError) as ex:
            _LOGGER.debug("Got error while setting the state: %s", ex)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.smartbulb.turn_off()

    @property
    def min_mireds(self):
        """Return minimum supported color temperature."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return maximum supported color temperature."""
        return self._max_mireds

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds for HA."""
        if self.smartbulb.color_temp is not None and self.smartbulb.color_temp != 0:
            return kelvin_to_mired(self.smartbulb.color_temp)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return brightness_from_percentage(self.smartbulb.brightness)

    @property
    def hs_color(self):
        """Return the color."""
        hue, sat, _ = self.smartbulb.hsv
        return hue, sat

    @property
    def is_on(self):
        """Return True if device is on."""
        return self.smartbulb.is_on

    async def async_update(self):
        """Update the TP-Link Bulb's state."""
        try:
            await self.smartbulb.update()
            self.update_emeter_state()

            self._supported_features = self.get_light_features()
            self._is_available = True
        except (SmartDeviceException, OSError) as ex:
            if self._is_available:
                _LOGGER.warning(
                    "Could not read data for %s: %s", self.smartbulb.host, ex
                )
            self._is_available = False

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def get_light_features(self):
        """Determine all supported features in one go."""
        supported_features = 0

        if self.smartbulb.is_dimmable:
            supported_features += SUPPORT_BRIGHTNESS
        if self.smartbulb.is_variable_color_temp:
            supported_features += SUPPORT_COLOR_TEMP
            self._min_mireds = kelvin_to_mired(
                self.smartbulb.valid_temperature_range[1]
            )
            self._max_mireds = kelvin_to_mired(
                self.smartbulb.valid_temperature_range[0]
            )
        if self.smartbulb.is_color:
            supported_features += SUPPORT_COLOR

        return supported_features

    def update_emeter_state(self):
        """Get the light state."""
        emeter_params = {}

        if self.smartbulb.has_emeter:
            emeter_params[ATTR_CURRENT_POWER_W] = "{:.1f}".format(
                self.smartbulb.emeter_realtime["power"]
            )

            consumption_today = self.smartbulb.emeter_today
            consumption_this_month = self.smartbulb.emeter_this_month
            if consumption_today is not None:
                emeter_params[ATTR_DAILY_ENERGY_KWH] = "{:.3f}".format(
                    consumption_today
                )
            if consumption_this_month is not None:
                emeter_params[ATTR_MONTHLY_ENERGY_KWH] = "{:.3f}".format(
                    consumption_this_month
                )

        self._device_state_attributes = emeter_params
