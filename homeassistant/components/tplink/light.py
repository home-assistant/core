"""Support for TPLink lights."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import re
import time
from typing import Any, NamedTuple, cast

from pyHS100 import SmartBulb, SmartDeviceException

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
import homeassistant.helpers.device_registry as dr
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)
import homeassistant.util.dt as dt_util

from . import CONF_LIGHT, DOMAIN as TPLINK_DOMAIN
from .common import add_available_devices

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=5)
CURRENT_POWER_UPDATE_INTERVAL = timedelta(seconds=60)
HISTORICAL_POWER_UPDATE_INTERVAL = timedelta(minutes=60)

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_POWER_W = "current_power_w"
ATTR_DAILY_ENERGY_KWH = "daily_energy_kwh"
ATTR_MONTHLY_ENERGY_KWH = "monthly_energy_kwh"

LIGHT_STATE_DFT_ON = "dft_on_state"
LIGHT_STATE_DFT_IGNORE = "ignore_default"
LIGHT_STATE_ON_OFF = "on_off"
LIGHT_STATE_RELAY_STATE = "relay_state"
LIGHT_STATE_BRIGHTNESS = "brightness"
LIGHT_STATE_COLOR_TEMP = "color_temp"
LIGHT_STATE_HUE = "hue"
LIGHT_STATE_SATURATION = "saturation"
LIGHT_STATE_ERROR_MSG = "err_msg"

LIGHT_SYSINFO_MAC = "mac"
LIGHT_SYSINFO_ALIAS = "alias"
LIGHT_SYSINFO_MODEL = "model"
LIGHT_SYSINFO_IS_DIMMABLE = "is_dimmable"
LIGHT_SYSINFO_IS_VARIABLE_COLOR_TEMP = "is_variable_color_temp"
LIGHT_SYSINFO_IS_COLOR = "is_color"

MAX_ATTEMPTS = 300
SLEEP_TIME = 2

TPLINK_KELVIN = {
    "LB130": (2500, 9000),
    "LB120": (2700, 6500),
    "LB230": (2500, 9000),
    "KB130": (2500, 9000),
    "KL130": (2500, 9000),
    "KL125": (2500, 6500),
    r"KL120\(EU\)": (2700, 6500),
    r"KL120\(US\)": (2700, 5000),
    r"KL430\(US\)": (2500, 9000),
}

FALLBACK_MIN_COLOR = 2700
FALLBACK_MAX_COLOR = 5000


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up lights."""
    entities = await hass.async_add_executor_job(
        add_available_devices, hass, CONF_LIGHT, TPLinkSmartBulb
    )

    if entities:
        async_add_entities(entities, update_before_add=True)

    if hass.data[TPLINK_DOMAIN][f"{CONF_LIGHT}_remaining"]:
        raise PlatformNotReady


def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return round((byt * 100.0) / 255.0)


def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return round((percent * 255.0) / 100.0)


class LightState(NamedTuple):
    """Light state."""

    state: bool
    brightness: int
    color_temp: float
    hs: tuple[int, int]

    def to_param(self):
        """Return a version that we can send to the bulb."""
        if self.color_temp:
            color_temp = mired_to_kelvin(self.color_temp)
        else:
            color_temp = None

        return {
            LIGHT_STATE_ON_OFF: 1 if self.state else 0,
            LIGHT_STATE_DFT_IGNORE: 1 if self.state else 0,
            LIGHT_STATE_BRIGHTNESS: brightness_to_percentage(self.brightness),
            LIGHT_STATE_COLOR_TEMP: color_temp,
            LIGHT_STATE_HUE: self.hs[0] if self.hs else 0,
            LIGHT_STATE_SATURATION: self.hs[1] if self.hs else 0,
        }


class LightFeatures(NamedTuple):
    """Light features."""

    sysinfo: dict[str, Any]
    mac: str
    alias: str
    model: str
    supported_features: int
    min_mireds: float
    max_mireds: float
    has_emeter: bool


class TPLinkSmartBulb(LightEntity):
    """Representation of a TPLink Smart Bulb."""

    def __init__(self, smartbulb: SmartBulb) -> None:
        """Initialize the bulb."""
        self.smartbulb = smartbulb
        self._light_features = cast(LightFeatures, None)
        self._light_state = cast(LightState, None)
        self._is_available = True
        self._is_setting_light_state = False
        self._last_current_power_update = None
        self._last_historical_power_update = None
        self._emeter_params = {}

        self._host = None
        self._alias = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._light_features.mac

    @property
    def name(self):
        """Return the name of the Smart Bulb."""
        return self._light_features.alias

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self._light_features.alias,
            "model": self._light_features.model,
            "manufacturer": "TP-Link",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._light_features.mac)},
            "sw_version": self._light_features.sysinfo["sw_ver"],
        }

    @property
    def available(self) -> bool:
        """Return if bulb is available."""
        return self._is_available

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._emeter_params

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
        elif self._light_state.brightness is not None:
            brightness = self._light_state.brightness
        else:
            brightness = 255

        if ATTR_COLOR_TEMP in kwargs:
            color_tmp = int(kwargs[ATTR_COLOR_TEMP])
        else:
            color_tmp = self._light_state.color_temp

        if ATTR_HS_COLOR in kwargs:
            # TP-Link requires integers.
            hue_sat = tuple(int(val) for val in kwargs[ATTR_HS_COLOR])

            # TP-Link cannot have both color temp and hue_sat
            color_tmp = 0
        else:
            hue_sat = self._light_state.hs

        await self._async_set_light_state_retry(
            self._light_state,
            self._light_state._replace(
                state=True,
                brightness=brightness,
                color_temp=color_tmp,
                hs=hue_sat,
            ),
        )

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._async_set_light_state_retry(
            self._light_state,
            self._light_state._replace(state=False),
        )

    @property
    def min_mireds(self):
        """Return minimum supported color temperature."""
        return self._light_features.min_mireds

    @property
    def max_mireds(self):
        """Return maximum supported color temperature."""
        return self._light_features.max_mireds

    @property
    def color_temp(self):
        """Return the color temperature of this light in mireds for HA."""
        return self._light_state.color_temp

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._light_state.brightness

    @property
    def hs_color(self):
        """Return the color."""
        return self._light_state.hs

    @property
    def is_on(self):
        """Return True if device is on."""
        return self._light_state.state

    def attempt_update(self, update_attempt):
        """Attempt to get details the TP-Link bulb."""
        # State is currently being set, ignore.
        if self._is_setting_light_state:
            return False

        try:
            if not self._light_features:
                self._light_features = self._get_light_features()
                self._alias = self._light_features.alias
                self._host = self.smartbulb.host
            self._light_state = self._get_light_state()
            return True

        except (SmartDeviceException, OSError) as ex:
            if update_attempt == 0:
                _LOGGER.debug(
                    "Retrying in %s seconds for %s|%s due to: %s",
                    SLEEP_TIME,
                    self._host,
                    self._alias,
                    ex,
                )
            return False

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._light_features.supported_features

    def _get_valid_temperature_range(self):
        """Return the device-specific white temperature range (in Kelvin).

        :return: White temperature range in Kelvin (minimum, maximum)
        """
        model = self.smartbulb.sys_info[LIGHT_SYSINFO_MODEL]
        for obj, temp_range in TPLINK_KELVIN.items():
            if re.match(obj, model):
                return temp_range
        # pyHS100 is abandoned, but some bulb definitions aren't present
        # use "safe" values for something that advertises color temperature
        return FALLBACK_MIN_COLOR, FALLBACK_MAX_COLOR

    def _get_light_features(self):
        """Determine all supported features in one go."""
        sysinfo = self.smartbulb.sys_info
        supported_features = 0
        # Calling api here as it reformats
        mac = self.smartbulb.mac
        alias = sysinfo[LIGHT_SYSINFO_ALIAS]
        model = sysinfo[LIGHT_SYSINFO_MODEL]
        min_mireds = None
        max_mireds = None
        has_emeter = self.smartbulb.has_emeter

        if sysinfo.get(LIGHT_SYSINFO_IS_DIMMABLE) or LIGHT_STATE_BRIGHTNESS in sysinfo:
            supported_features += SUPPORT_BRIGHTNESS
        if sysinfo.get(LIGHT_SYSINFO_IS_VARIABLE_COLOR_TEMP):
            supported_features += SUPPORT_COLOR_TEMP
            max_range, min_range = self._get_valid_temperature_range()
            min_mireds = kelvin_to_mired(min_range)
            max_mireds = kelvin_to_mired(max_range)
        if sysinfo.get(LIGHT_SYSINFO_IS_COLOR):
            supported_features += SUPPORT_COLOR

        return LightFeatures(
            sysinfo=sysinfo,
            mac=mac,
            alias=alias,
            model=model,
            supported_features=supported_features,
            min_mireds=min_mireds,
            max_mireds=max_mireds,
            has_emeter=has_emeter,
        )

    def _light_state_from_params(self, light_state_params) -> LightState:
        brightness = None
        color_temp = None
        hue_saturation = None
        light_features = self._light_features

        state = bool(light_state_params[LIGHT_STATE_ON_OFF])

        if not state and LIGHT_STATE_DFT_ON in light_state_params:
            light_state_params = light_state_params[LIGHT_STATE_DFT_ON]

        if light_features.supported_features & SUPPORT_BRIGHTNESS:
            brightness = brightness_from_percentage(
                light_state_params[LIGHT_STATE_BRIGHTNESS]
            )

        if (
            light_features.supported_features & SUPPORT_COLOR_TEMP
            and light_state_params.get(LIGHT_STATE_COLOR_TEMP) is not None
            and light_state_params[LIGHT_STATE_COLOR_TEMP] != 0
        ):
            color_temp = kelvin_to_mired(light_state_params[LIGHT_STATE_COLOR_TEMP])

        if color_temp is None and light_features.supported_features & SUPPORT_COLOR:
            hue_saturation = (
                light_state_params[LIGHT_STATE_HUE],
                light_state_params[LIGHT_STATE_SATURATION],
            )

        return LightState(
            state=state,
            brightness=brightness,
            color_temp=color_temp,
            hs=hue_saturation,
        )

    def _get_light_state(self) -> LightState:
        """Get the light state."""
        self._update_emeter()
        return self._light_state_from_params(self._get_device_state())

    def _update_emeter(self):
        if not self._light_features.has_emeter:
            return

        now = dt_util.utcnow()
        if (
            not self._last_current_power_update
            or self._last_current_power_update + CURRENT_POWER_UPDATE_INTERVAL < now
        ):
            self._last_current_power_update = now
            self._emeter_params[ATTR_CURRENT_POWER_W] = round(
                float(self.smartbulb.current_consumption()), 1
            )

        if (
            not self._last_historical_power_update
            or self._last_historical_power_update + HISTORICAL_POWER_UPDATE_INTERVAL
            < now
        ):
            self._last_historical_power_update = now
            daily_statistics = self.smartbulb.get_emeter_daily()
            monthly_statistics = self.smartbulb.get_emeter_monthly()
            try:
                self._emeter_params[ATTR_DAILY_ENERGY_KWH] = round(
                    float(daily_statistics[int(time.strftime("%d"))]), 3
                )
                self._emeter_params[ATTR_MONTHLY_ENERGY_KWH] = round(
                    float(monthly_statistics[int(time.strftime("%m"))]), 3
                )
            except KeyError:
                # device returned no daily/monthly history
                pass

    async def _async_set_light_state_retry(
        self, old_light_state: LightState, new_light_state: LightState
    ) -> None:
        """Set the light state with retry."""
        # Tell the device to set the states.
        if not _light_state_diff(old_light_state, new_light_state):
            # Nothing to do, avoid the executor
            return

        self._is_setting_light_state = True
        try:
            light_state_params = await self.hass.async_add_executor_job(
                self._set_light_state, old_light_state, new_light_state
            )
            self._is_available = True
            self._is_setting_light_state = False
            if LIGHT_STATE_ERROR_MSG in light_state_params:
                raise HomeAssistantError(light_state_params[LIGHT_STATE_ERROR_MSG])
            self._light_state = self._light_state_from_params(light_state_params)
            return
        except (SmartDeviceException, OSError):
            pass

        try:
            _LOGGER.debug("Retrying setting light state")
            light_state_params = await self.hass.async_add_executor_job(
                self._set_light_state, old_light_state, new_light_state
            )
            self._is_available = True
            if LIGHT_STATE_ERROR_MSG in light_state_params:
                raise HomeAssistantError(light_state_params[LIGHT_STATE_ERROR_MSG])
            self._light_state = self._light_state_from_params(light_state_params)
        except (SmartDeviceException, OSError) as ex:
            self._is_available = False
            _LOGGER.warning("Could not set data for %s: %s", self.smartbulb.host, ex)

        self._is_setting_light_state = False

    def _set_light_state(
        self, old_light_state: LightState, new_light_state: LightState
    ) -> None:
        """Set the light state."""
        diff = _light_state_diff(old_light_state, new_light_state)

        if not diff:
            return

        return self._set_device_state(diff)

    def _get_device_state(self):
        """State of the bulb or smart dimmer switch."""
        if isinstance(self.smartbulb, SmartBulb):
            return self.smartbulb.get_light_state()

        sysinfo = self.smartbulb.sys_info
        # Its not really a bulb, its a dimmable SmartPlug (aka Wall Switch)
        return {
            LIGHT_STATE_ON_OFF: sysinfo[LIGHT_STATE_RELAY_STATE],
            LIGHT_STATE_BRIGHTNESS: sysinfo.get(LIGHT_STATE_BRIGHTNESS, 0),
            LIGHT_STATE_COLOR_TEMP: 0,
            LIGHT_STATE_HUE: 0,
            LIGHT_STATE_SATURATION: 0,
        }

    def _set_device_state(self, state):
        """Set state of the bulb or smart dimmer switch."""
        if isinstance(self.smartbulb, SmartBulb):
            return self.smartbulb.set_light_state(state)

        # Its not really a bulb, its a dimmable SmartPlug (aka Wall Switch)
        if LIGHT_STATE_BRIGHTNESS in state:
            # Brightness of 0 is accepted by the
            # device but the underlying library rejects it
            # so we turn off instead.
            if state[LIGHT_STATE_BRIGHTNESS]:
                self.smartbulb.brightness = state[LIGHT_STATE_BRIGHTNESS]
            else:
                self.smartbulb.state = self.smartbulb.SWITCH_STATE_OFF
        elif LIGHT_STATE_ON_OFF in state:
            if state[LIGHT_STATE_ON_OFF]:
                self.smartbulb.state = self.smartbulb.SWITCH_STATE_ON
            else:
                self.smartbulb.state = self.smartbulb.SWITCH_STATE_OFF

        return self._get_device_state()

    async def async_update(self):
        """Update the TP-Link bulb's state."""
        for update_attempt in range(MAX_ATTEMPTS):
            is_ready = await self.hass.async_add_executor_job(
                self.attempt_update, update_attempt
            )

            if is_ready:
                self._is_available = True
                if update_attempt > 0:
                    _LOGGER.debug(
                        "Device %s|%s responded after %s attempts",
                        self._host,
                        self._alias,
                        update_attempt,
                    )
                break
            await asyncio.sleep(SLEEP_TIME)
        else:
            if self._is_available:
                _LOGGER.warning(
                    "Could not read state for %s|%s",
                    self._host,
                    self._alias,
                )
            self._is_available = False


def _light_state_diff(old_light_state: LightState, new_light_state: LightState):
    old_state_param = old_light_state.to_param()
    new_state_param = new_light_state.to_param()

    return {
        key: value
        for key, value in new_state_param.items()
        if new_state_param.get(key) != old_state_param.get(key)
    }
