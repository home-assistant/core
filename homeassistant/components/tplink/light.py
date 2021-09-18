"""Support for TPLink lights."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time
from typing import Any, NamedTuple, cast

from kasa import SmartBulb, SmartDeviceException

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
LIGHT_STATE_TRANSITION = "transition"
LIGHT_STATE_ERROR_MSG = "err_msg"

LIGHT_SYSINFO_MAC = "mac"
LIGHT_SYSINFO_ALIAS = "alias"
LIGHT_SYSINFO_MODEL = "model"
LIGHT_SYSINFO_IS_DIMMABLE = "is_dimmable"
LIGHT_SYSINFO_IS_VARIABLE_COLOR_TEMP = "is_variable_color_temp"
LIGHT_SYSINFO_IS_COLOR = "is_color"

MAX_ATTEMPTS = 300
SLEEP_TIME = 2


class ColorTempRange(NamedTuple):
    """Color temperature range (in Kelvin)."""

    min: int
    max: int


FALLBACK_MIN_COLOR = 2700
FALLBACK_MAX_COLOR = 5000


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lights."""
    entities = await add_available_devices(hass, CONF_LIGHT, TPLinkSmartBulb)

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
    transition: int = 0

    def to_param(self):
        """Return a version that we can send to the bulb."""
        color_temp = None
        if self.color_temp:
            color_temp = mired_to_kelvin(self.color_temp)

        return {
            LIGHT_STATE_ON_OFF: 1 if self.state else 0,
            LIGHT_STATE_DFT_IGNORE: 1 if self.state else 0,
            LIGHT_STATE_BRIGHTNESS: brightness_to_percentage(self.brightness),
            LIGHT_STATE_COLOR_TEMP: color_temp,
            LIGHT_STATE_HUE: self.hs[0] if self.hs else 0,
            LIGHT_STATE_SATURATION: self.hs[1] if self.hs else 0,
            LIGHT_STATE_TRANSITION: self.transition,
        }


class TPLinkSmartBulb(LightEntity):
    """Representation of a TPLink Smart Bulb."""

    def __init__(self, smartbulb: SmartBulb) -> None:
        """Initialize the bulb."""
        self.smartbulb = smartbulb
        self._light_state = cast(LightState, None)
        self._is_available = True
        self._is_setting_light_state = False
        self._last_current_power_update = None
        self._last_historical_power_update = None
        self._emeter_params = {}

        self._host = None
        self._alias = None

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self.smartbulb.device_id

    @property
    def name(self) -> str | None:
        """Return the name of the Smart Bulb."""
        return self.smartbulb.alias

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return {
            "name": self.smartbulb.alias,
            "model": self.smartbulb.model,
            "manufacturer": "TP-Link",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.smartbulb.device_id)},
            "sw_version": self.smartbulb.hw_info["sw_ver"],
        }

    @property
    def available(self) -> bool:
        """Return if bulb is available."""
        return self._is_available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
        elif self._light_state.brightness is not None:
            brightness = self.smartbulb.brightness
        else:
            brightness = 255

        if ATTR_COLOR_TEMP in kwargs:
            color_tmp = int(kwargs[ATTR_COLOR_TEMP])
        else:
            color_tmp = self.smartbulb.color_temp

        if ATTR_HS_COLOR in kwargs:
            # TP-Link requires integers.
            hue_sat = tuple(int(val) for val in kwargs[ATTR_HS_COLOR])

            # TP-Link cannot have both color temp and hue_sat
            color_tmp = 0
        else:
            hue_sat = self.hs_color

        await self._async_set_light_state_retry(
            self._light_state,
            self._light_state._replace(
                state=True,
                brightness=brightness,
                color_temp=color_tmp,
                hs=hue_sat,
            ),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.smartbulb.turn_off(transition=kwargs.get(ATTR_TRANSITION, 0))

    @property
    def min_mireds(self) -> int:
        """Return minimum supported color temperature."""
        try:
            ct = self.smartbulb.valid_temperature_range[0]
        except SmartDeviceException:
            ct = FALLBACK_MAX_COLOR
        finally:
            return kelvin_to_mired(ct)

    @property
    def max_mireds(self) -> int:
        """Return maximum supported color temperature."""
        try:
            ct = self.smartbulb.valid_temperature_range[1]
        except SmartDeviceException:
            ct = FALLBACK_MAX_COLOR
        finally:
            return kelvin_to_mired(ct)

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature of this light in mireds for HA."""
        return self.smartbulb.color_temp

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self.smartbulb.brightness

    @property
    def hs_color(self) -> tuple[int, int] | None:
        """Return the color."""
        h, s, _ = self.smartbulb.hsv
        return h, s

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.smartbulb.is_on

    async def attempt_update(self, update_attempt: int) -> bool:
        """Attempt to get details the TP-Link bulb."""
        # State is currently being set, ignore.
        if self._is_setting_light_state:
            return False

        try:
            self._light_state = await self._get_light_state()
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
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features = 0

        if self.smartbulb.is_dimmable:
            supported_features += SUPPORT_BRIGHTNESS
        if self.smartbulb.is_variable_color_temp:
            supported_features += SUPPORT_COLOR_TEMP
        if self.smartbulb.is_color:
            supported_features += SUPPORT_COLOR

        return supported_features

    def _light_state_from_params(self, light_state_params: Any) -> LightState:
        brightness = None
        color_temp = None
        hue_saturation = None

        state = bool(light_state_params[LIGHT_STATE_ON_OFF])

        if not state and LIGHT_STATE_DFT_ON in light_state_params:
            light_state_params = light_state_params[LIGHT_STATE_DFT_ON]

        if self.supported_features & SUPPORT_BRIGHTNESS:
            brightness = brightness_from_percentage(
                light_state_params[LIGHT_STATE_BRIGHTNESS]
            )

        if (
            self.supported_features & SUPPORT_COLOR_TEMP
            and light_state_params.get(LIGHT_STATE_COLOR_TEMP) is not None
            and light_state_params[LIGHT_STATE_COLOR_TEMP] != 0
        ):
            color_temp = kelvin_to_mired(light_state_params[LIGHT_STATE_COLOR_TEMP])

        if color_temp is None and self.supported_features & SUPPORT_COLOR:
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

    async def _get_light_state(self) -> LightState:
        """Get the light state."""
        await self._update_emeter()
        return self._light_state_from_params(await self._get_device_state())

    async def _update_emeter(self) -> None:
        if not self.smartbulb.has_emeter:
            return

        now = dt_util.utcnow()
        if (
            not self._last_current_power_update
            or self._last_current_power_update + CURRENT_POWER_UPDATE_INTERVAL < now
        ):
            self._last_current_power_update = now
            self._emeter_params[ATTR_CURRENT_POWER_W] = round(
                float(await self.smartbulb.current_consumption()), 1
            )

        if (
            not self._last_historical_power_update
            or self._last_historical_power_update + HISTORICAL_POWER_UPDATE_INTERVAL
            < now
        ):
            self._last_historical_power_update = now
            daily_statistics = await self.smartbulb.get_emeter_daily()
            monthly_statistics = await self.smartbulb.get_emeter_monthly()
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
        for attempt in range(MAX_ATTEMPTS):
            try:
                light_state_params = await self._set_light_state(
                    old_light_state, new_light_state
                )
                self._is_available = True
                self._is_setting_light_state = False
                if LIGHT_STATE_ERROR_MSG in light_state_params:
                    raise HomeAssistantError(light_state_params[LIGHT_STATE_ERROR_MSG])
                # Some devices do not report the new state in their responses, so we skip
                # set here and wait for the next poll to update the values. See #47600
                if LIGHT_STATE_ON_OFF in light_state_params:
                    self._light_state = self._light_state_from_params(
                        light_state_params
                    )

                self._is_setting_light_state = False
                return
            except (SmartDeviceException, OSError) as ex:
                _LOGGER.warning(
                    "Could not set data for %s: %s", self.smartbulb.host, ex
                )

        self._is_available = False
        self._is_setting_light_state = False
        _LOGGER.warning(
            "Could not set data for %s after tries bailing out", self.smartbulb.host
        )

    async def _set_light_state(
        self, old_light_state: LightState, new_light_state: LightState
    ) -> dict:
        """Set the light state."""
        diff = _light_state_diff(old_light_state, new_light_state)

        if not diff:
            return {}

        return await self._set_device_state(diff)

    async def _get_device_state(self) -> dict:
        """State of the bulb or smart dimmer switch."""
        if self.smartbulb.is_bulb:
            return await self.smartbulb.get_light_state()

        sysinfo = self.smartbulb.sys_info
        # Its not really a bulb, its a dimmable SmartPlug (aka Wall Switch)
        return {
            LIGHT_STATE_ON_OFF: sysinfo[LIGHT_STATE_RELAY_STATE],
            LIGHT_STATE_BRIGHTNESS: sysinfo.get(LIGHT_STATE_BRIGHTNESS, 0),
            LIGHT_STATE_COLOR_TEMP: 0,
            LIGHT_STATE_HUE: 0,
            LIGHT_STATE_SATURATION: 0,
        }

    async def _set_device_state(self, state):
        """Set state of the bulb or smart dimmer switch."""
        if self.smartbulb.is_bulb:
            return await self.smartbulb.set_light_state(state)

        # Its not really a bulb, its a dimmable SmartPlug (aka Wall Switch)
        if LIGHT_STATE_BRIGHTNESS in state:
            # Brightness of 0 is accepted by the
            # device but the underlying library rejects it
            # so we turn off instead.
            if state[LIGHT_STATE_BRIGHTNESS]:
                await self.smartbulb.set_brightness(state[LIGHT_STATE_BRIGHTNESS])
            else:
                await self.smartbulb.turn_off()
        elif LIGHT_STATE_ON_OFF in state:
            if state[LIGHT_STATE_ON_OFF]:
                await self.smartbulb.turn_on()
            else:
                await self.smartbulb.turn_off()

        return await self._get_device_state()

    async def async_update(self) -> None:
        """Update the TP-Link bulb's state."""
        for update_attempt in range(MAX_ATTEMPTS):
            is_ready = await self.attempt_update(update_attempt)

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


def _light_state_diff(
    old_light_state: LightState, new_light_state: LightState
) -> dict[str, Any]:
    old_state_param = old_light_state.to_param()
    new_state_param = new_light_state.to_param()

    return {
        key: value
        for key, value in new_state_param.items()
        if new_state_param.get(key) != old_state_param.get(key)
    }
