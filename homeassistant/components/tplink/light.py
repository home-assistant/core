"""Support for TPLink lights."""
from datetime import timedelta
import logging
import time
from typing import Any, Dict, NamedTuple, Tuple, cast

from pyHS100 import SmartBulb, SmartDeviceException

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    Light,
)
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)
import homeassistant.util.dt as dt_util

from . import CONF_LIGHT, DOMAIN as TPLINK_DOMAIN
from .common import async_add_entities_retry

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=5)
CURRENT_POWER_UPDATE_INTERVAL = timedelta(seconds=60)
HISTORICAL_POWER_UPDATE_INTERVAL = timedelta(minutes=60)

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_POWER_W = "current_power_w"
ATTR_DAILY_ENERGY_KWH = "daily_energy_kwh"
ATTR_MONTHLY_ENERGY_KWH = "monthly_energy_kwh"

LIGHT_STATE_DFT_ON = "dft_on_state"
LIGHT_STATE_ON_OFF = "on_off"
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


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform.

    Deprecated.
    """
    _LOGGER.warning(
        "Loading as a platform is no longer supported, "
        "convert to use the tplink component."
    )


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    """Set up switches."""
    await async_add_entities_retry(
        hass, async_add_entities, hass.data[TPLINK_DOMAIN][CONF_LIGHT], add_entity
    )

    return True


def add_entity(device: SmartBulb, async_add_entities):
    """Check if device is online and add the entity."""
    # Attempt to get the sysinfo. If it fails, it will raise an
    # exception that is caught by async_add_entities_retry which
    # will try again later.
    device.get_sysinfo()

    async_add_entities([TPLinkSmartBulb(device)], update_before_add=True)


def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return int((byt * 100.0) / 255.0)


def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return (percent * 255.0) / 100.0


class LightState(NamedTuple):
    """Light state."""

    state: bool
    brightness: int
    color_temp: float
    hs: Tuple[int, int]

    def to_param(self):
        """Return a version that we can send to the bulb."""
        if self.color_temp:
            color_temp = mired_to_kelvin(self.color_temp)
        else:
            color_temp = None

        return {
            LIGHT_STATE_ON_OFF: 1 if self.state else 0,
            LIGHT_STATE_BRIGHTNESS: brightness_to_percentage(self.brightness),
            LIGHT_STATE_COLOR_TEMP: color_temp,
            LIGHT_STATE_HUE: self.hs[0] if self.hs else 0,
            LIGHT_STATE_SATURATION: self.hs[1] if self.hs else 0,
        }


class LightFeatures(NamedTuple):
    """Light features."""

    sysinfo: Dict[str, Any]
    mac: str
    alias: str
    model: str
    supported_features: int
    min_mireds: float
    max_mireds: float


class TPLinkSmartBulb(Light):
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
    def device_state_attributes(self):
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
                state=True, brightness=brightness, color_temp=color_tmp, hs=hue_sat,
            ),
        )

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._async_set_light_state_retry(
            self._light_state, self._light_state._replace(state=False),
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

    def update(self):
        """Update the TP-Link Bulb's state."""
        # State is currently being set, ignore.
        if self._is_setting_light_state:
            return

        try:
            # Update light features only once.
            if not self._light_features:
                self._light_features = self._get_light_features_retry()
            self._light_state = self._get_light_state_retry()
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
        return self._light_features.supported_features

    def _get_light_features_retry(self) -> LightFeatures:
        """Retry the retrieval of the supported features."""
        try:
            return self._get_light_features()
        except (SmartDeviceException, OSError):
            pass

        _LOGGER.debug("Retrying getting light features")
        return self._get_light_features()

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

        if sysinfo.get(LIGHT_SYSINFO_IS_DIMMABLE):
            supported_features += SUPPORT_BRIGHTNESS
        if sysinfo.get(LIGHT_SYSINFO_IS_VARIABLE_COLOR_TEMP):
            supported_features += SUPPORT_COLOR_TEMP
            # Have to make another api request here in
            # order to not re-implement pyHS100 here
            max_range, min_range = self.smartbulb.valid_temperature_range
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
        )

    def _get_light_state_retry(self) -> LightState:
        """Retry the retrieval of getting light states."""
        try:
            return self._get_light_state()
        except (SmartDeviceException, OSError):
            pass

        _LOGGER.debug("Retrying getting light state")
        return self._get_light_state()

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

        if light_features.supported_features & SUPPORT_COLOR_TEMP:
            if (
                light_state_params.get(LIGHT_STATE_COLOR_TEMP) is not None
                and light_state_params[LIGHT_STATE_COLOR_TEMP] != 0
            ):
                color_temp = kelvin_to_mired(light_state_params[LIGHT_STATE_COLOR_TEMP])

        if light_features.supported_features & SUPPORT_COLOR:
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
        return self._light_state_from_params(self.smartbulb.get_light_state())

    def _update_emeter(self):
        if not self.smartbulb.has_emeter:
            return

        now = dt_util.utcnow()
        if (
            not self._last_current_power_update
            or self._last_current_power_update + CURRENT_POWER_UPDATE_INTERVAL < now
        ):
            self._last_current_power_update = now
            self._emeter_params[ATTR_CURRENT_POWER_W] = "{:.1f}".format(
                self.smartbulb.current_consumption()
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
                self._emeter_params[ATTR_DAILY_ENERGY_KWH] = "{:.3f}".format(
                    daily_statistics[int(time.strftime("%d"))]
                )
                self._emeter_params[ATTR_MONTHLY_ENERGY_KWH] = "{:.3f}".format(
                    monthly_statistics[int(time.strftime("%m"))]
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

        return self.smartbulb.set_light_state(diff)


def _light_state_diff(old_light_state: LightState, new_light_state: LightState):
    old_state_param = old_light_state.to_param()
    new_state_param = new_light_state.to_param()

    return {
        key: value
        for key, value in new_state_param.items()
        if new_state_param.get(key) != old_state_param.get(key)
    }
