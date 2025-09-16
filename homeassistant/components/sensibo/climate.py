"""Support for Sensibo climate devices."""

from __future__ import annotations

from bisect import bisect_left
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_MODE,
    ATTR_STATE,
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from . import SensiboConfigEntry
from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, async_handle_api_call

SERVICE_ASSUME_STATE = "assume_state"
SERVICE_ENABLE_TIMER = "enable_timer"
ATTR_MINUTES = "minutes"
SERVICE_ENABLE_PURE_BOOST = "enable_pure_boost"
SERVICE_DISABLE_PURE_BOOST = "disable_pure_boost"
SERVICE_FULL_STATE = "full_state"
SERVICE_ENABLE_CLIMATE_REACT = "enable_climate_react"
SERVICE_GET_DEVICE_CAPABILITIES = "get_device_capabilities"
ATTR_HIGH_TEMPERATURE_THRESHOLD = "high_temperature_threshold"
ATTR_HIGH_TEMPERATURE_STATE = "high_temperature_state"
ATTR_LOW_TEMPERATURE_THRESHOLD = "low_temperature_threshold"
ATTR_LOW_TEMPERATURE_STATE = "low_temperature_state"
ATTR_SMART_TYPE = "smart_type"

ATTR_AC_INTEGRATION = "ac_integration"
ATTR_GEO_INTEGRATION = "geo_integration"
ATTR_INDOOR_INTEGRATION = "indoor_integration"
ATTR_OUTDOOR_INTEGRATION = "outdoor_integration"
ATTR_SENSITIVITY = "sensitivity"
ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_HORIZONTAL_SWING_MODE = "horizontal_swing_mode"
ATTR_LIGHT = "light"
BOOST_INCLUSIVE = "boost_inclusive"

AVAILABLE_FAN_MODES = {
    "quiet",
    "low",
    "medium_low",
    "medium",
    "medium_high",
    "high",
    "strong",
    "auto",
}
AVAILABLE_SWING_MODES = {
    "stopped",
    "fixedtop",
    "fixedmiddletop",
    "fixedmiddle",
    "fixedmiddlebottom",
    "fixedbottom",
    "rangetop",
    "rangemiddle",
    "rangebottom",
    "rangefull",
    "horizontal",
    "both",
}
AVAILABLE_HORIZONTAL_SWING_MODES = {
    "stopped",
    "fixedleft",
    "fixedcenterleft",
    "fixedcenter",
    "fixedcenterright",
    "fixedright",
    "fixedleftright",
    "rangecenter",
    "rangefull",
    "rangeleft",
    "rangeright",
    "horizontal",
    "both",
}

PARALLEL_UPDATES = 0

FIELD_TO_FLAG = {
    "fanLevel": ClimateEntityFeature.FAN_MODE,
    "swing": ClimateEntityFeature.SWING_MODE,
    "horizontalSwing": ClimateEntityFeature.SWING_HORIZONTAL_MODE,
    "targetTemperature": ClimateEntityFeature.TARGET_TEMPERATURE,
}

SENSIBO_TO_HA = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "fan": HVACMode.FAN_ONLY,
    "auto": HVACMode.HEAT_COOL,
    "dry": HVACMode.DRY,
    "off": HVACMode.OFF,
}

HA_TO_SENSIBO = {value: key for key, value in SENSIBO_TO_HA.items()}

AC_STATE_TO_DATA = {
    "targetTemperature": "target_temp",
    "fanLevel": "fan_mode",
    "on": "device_on",
    "mode": "hvac_mode",
    "swing": "swing_mode",
    "horizontalSwing": "horizontal_swing_mode",
}


def _find_valid_target_temp(target: float, valid_targets: list[int]) -> int:
    if target <= valid_targets[0]:
        return valid_targets[0]
    if target >= valid_targets[-1]:
        return valid_targets[-1]
    return valid_targets[bisect_left(valid_targets, target)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiboConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sensibo climate entry."""

    coordinator = entry.runtime_data

    added_devices: set[str] = set()

    def _add_remove_devices() -> None:
        """Handle additions of devices and sensors."""
        nonlocal added_devices
        new_devices, _, new_added_devices = coordinator.get_devices(added_devices)
        added_devices = new_added_devices

        if new_devices:
            async_add_entities(
                SensiboClimate(coordinator, device_id)
                for device_id in coordinator.data.parsed
                if device_id in new_devices
            )

    entry.async_on_unload(coordinator.async_add_listener(_add_remove_devices))
    _add_remove_devices()

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_ASSUME_STATE,
        {
            vol.Required(ATTR_STATE): vol.In(["on", "off"]),
        },
        "async_assume_state",
    )
    platform.async_register_entity_service(
        SERVICE_ENABLE_TIMER,
        {
            vol.Required(ATTR_MINUTES): cv.positive_int,
        },
        "async_enable_timer",
    )
    platform.async_register_entity_service(
        SERVICE_ENABLE_PURE_BOOST,
        {
            vol.Required(ATTR_AC_INTEGRATION): bool,
            vol.Required(ATTR_GEO_INTEGRATION): bool,
            vol.Required(ATTR_INDOOR_INTEGRATION): bool,
            vol.Required(ATTR_OUTDOOR_INTEGRATION): bool,
            vol.Required(ATTR_SENSITIVITY): vol.In(["normal", "sensitive"]),
        },
        "async_enable_pure_boost",
    )
    platform.async_register_entity_service(
        SERVICE_FULL_STATE,
        {
            vol.Required(ATTR_MODE): vol.In(
                ["cool", "heat", "fan", "auto", "dry", "off"]
            ),
            vol.Optional(ATTR_TARGET_TEMPERATURE): int,
            vol.Optional(ATTR_FAN_MODE): str,
            vol.Optional(ATTR_SWING_MODE): str,
            vol.Optional(ATTR_HORIZONTAL_SWING_MODE): str,
            vol.Optional(ATTR_LIGHT): vol.In(["on", "off", "dim"]),
        },
        "async_full_ac_state",
    )
    platform.async_register_entity_service(
        SERVICE_ENABLE_CLIMATE_REACT,
        {
            vol.Required(ATTR_HIGH_TEMPERATURE_THRESHOLD): vol.Coerce(float),
            vol.Required(ATTR_HIGH_TEMPERATURE_STATE): dict,
            vol.Required(ATTR_LOW_TEMPERATURE_THRESHOLD): vol.Coerce(float),
            vol.Required(ATTR_LOW_TEMPERATURE_STATE): dict,
            vol.Required(ATTR_SMART_TYPE): vol.In(
                ["temperature", "feelslike", "humidity"]
            ),
        },
        "async_enable_climate_react",
    )
    platform.async_register_entity_service(
        SERVICE_GET_DEVICE_CAPABILITIES,
        {vol.Required(ATTR_HVAC_MODE): vol.Coerce(HVACMode)},
        "async_get_device_capabilities",
        supports_response=SupportsResponse.ONLY,
    )


class SensiboClimate(SensiboDeviceBaseEntity, ClimateEntity):
    """Representation of a Sensibo climate device."""

    _attr_name = None
    _attr_precision = PRECISION_TENTHS
    _attr_translation_key = "climate_device"

    def __init__(
        self, coordinator: SensiboDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initiate Sensibo Climate."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = device_id
        self._attr_temperature_unit = (
            UnitOfTemperature.CELSIUS
            if self.device_data.temp_unit == "C"
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        for key in self.device_data.active_features:
            if key in FIELD_TO_FLAG:
                features |= FIELD_TO_FLAG[key]
        return features

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self.device_data.humidity

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation."""
        if self.device_data.device_on and self.device_data.hvac_mode:
            return SENSIBO_TO_HA[self.device_data.hvac_mode]
        return HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        if TYPE_CHECKING:
            assert self.device_data.hvac_modes
        return [SENSIBO_TO_HA[mode] for mode in self.device_data.hvac_modes]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.device_data.temp:
            return TemperatureConverter.convert(
                self.device_data.temp,
                UnitOfTemperature.CELSIUS,
                self.temperature_unit,
            )
        return None

    @property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return (
            UnitOfTemperature.CELSIUS
            if self.device_data.temp_unit == "C"
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.device_data.target_temp

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self.device_data.temp_step

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self.device_data.fan_mode

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes."""
        return self.device_data.fan_modes

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return self.device_data.swing_mode

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes."""
        return self.device_data.swing_modes

    @property
    def swing_horizontal_mode(self) -> str | None:
        """Return the horizontal swing setting."""
        return self.device_data.horizontal_swing_mode

    @property
    def swing_horizontal_modes(self) -> list[str] | None:
        """Return the list of available horizontal swing modes."""
        return self.device_data.horizontal_swing_modes

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.device_data.temp_list[0]

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.device_data.temp_list[-1]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature: float = kwargs[ATTR_TEMPERATURE]
        if temperature == self.target_temperature:
            return

        new_temp = _find_valid_target_temp(temperature, self.device_data.temp_list)
        await self.async_send_api_call(
            key=AC_STATE_TO_DATA["targetTemperature"],
            value=new_temp,
            name="targetTemperature",
            assumed_state=False,
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode not in AVAILABLE_FAN_MODES:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="fan_mode_not_supported",
                translation_placeholders={"fan_mode": fan_mode},
            )

        transformation = self.device_data.fan_modes_translated
        await self.async_send_api_call(
            key=AC_STATE_TO_DATA["fanLevel"],
            value=fan_mode,
            name="fanLevel",
            assumed_state=False,
            transformation=transformation,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_send_api_call(
                key=AC_STATE_TO_DATA["on"],
                value=False,
                name="on",
                assumed_state=False,
            )
            return

        # Turn on if not currently on.
        if not self.device_data.device_on:
            await self.async_send_api_call(
                key=AC_STATE_TO_DATA["on"],
                value=True,
                name="on",
                assumed_state=False,
            )

        await self.async_send_api_call(
            key=AC_STATE_TO_DATA["mode"],
            value=HA_TO_SENSIBO[hvac_mode],
            name="mode",
            assumed_state=False,
        )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        if swing_mode not in AVAILABLE_SWING_MODES:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="swing_not_supported",
                translation_placeholders={"swing_mode": swing_mode},
            )

        transformation = self.device_data.swing_modes_translated
        await self.async_send_api_call(
            key=AC_STATE_TO_DATA["swing"],
            value=swing_mode,
            name="swing",
            assumed_state=False,
            transformation=transformation,
        )

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new target horizontal swing operation."""
        if swing_horizontal_mode not in AVAILABLE_HORIZONTAL_SWING_MODES:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="horizontal_swing_not_supported",
                translation_placeholders={
                    "horizontal_swing_mode": swing_horizontal_mode
                },
            )

        transformation = self.device_data.horizontal_swing_modes_translated
        await self.async_send_api_call(
            key=AC_STATE_TO_DATA["horizontalSwing"],
            value=swing_horizontal_mode,
            name="horizontalSwing",
            assumed_state=False,
            transformation=transformation,
        )

    async def async_turn_on(self) -> None:
        """Turn Sensibo unit on."""
        await self.async_send_api_call(
            key=AC_STATE_TO_DATA["on"],
            value=True,
            name="on",
            assumed_state=False,
        )

    async def async_turn_off(self) -> None:
        """Turn Sensibo unit on."""
        await self.async_send_api_call(
            key=AC_STATE_TO_DATA["on"],
            value=False,
            name="on",
            assumed_state=False,
        )

    async def async_get_device_capabilities(
        self, hvac_mode: HVACMode
    ) -> dict[str, Any]:
        """Get capabilities from device."""
        active_features = self.device_data.active_features
        mode_capabilities: dict[str, Any] | None = self.device_data.full_capabilities[
            "modes"
        ].get(hvac_mode.value)
        if not mode_capabilities:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="mode_not_exist"
            )
        remote_capabilities: dict[str, Any] = {}
        for active_feature in active_features:
            if active_feature in mode_capabilities:
                remote_capabilities[active_feature.lower()] = mode_capabilities[
                    active_feature
                ]
        return remote_capabilities

    async def async_assume_state(self, state: str) -> None:
        """Sync state with api."""
        await self.async_send_api_call(
            key=AC_STATE_TO_DATA["on"],
            value=state != HVACMode.OFF,
            name="on",
            assumed_state=True,
        )

    async def async_full_ac_state(
        self,
        mode: str,
        target_temperature: int | None = None,
        fan_mode: str | None = None,
        swing_mode: str | None = None,
        horizontal_swing_mode: str | None = None,
        light: str | None = None,
    ) -> None:
        """Set full AC state."""
        new_ac_state = self.device_data.ac_states
        new_ac_state.pop("timestamp")
        new_ac_state["on"] = False
        if mode != "off":
            new_ac_state["on"] = True
            new_ac_state["mode"] = mode
        if target_temperature:
            new_ac_state["targetTemperature"] = target_temperature
        if fan_mode:
            new_ac_state["fanLevel"] = fan_mode
        if swing_mode:
            new_ac_state["swing"] = swing_mode
        if horizontal_swing_mode:
            new_ac_state["horizontalSwing"] = horizontal_swing_mode
        if light:
            new_ac_state["light"] = light

        await self.api_call_custom_service_full_ac_state(
            key="hvac_mode", value=mode, data=new_ac_state
        )

    async def async_enable_timer(self, minutes: int) -> None:
        """Enable the timer."""
        new_state = bool(self.device_data.ac_states["on"] is False)
        params = {
            "minutesFromNow": minutes,
            "acState": {**self.device_data.ac_states, "on": new_state},
        }
        await self.api_call_custom_service_timer(
            key="timer_on",
            value=True,
            data=params,
        )

    async def async_enable_pure_boost(
        self,
        ac_integration: bool | None = None,
        geo_integration: bool | None = None,
        indoor_integration: bool | None = None,
        outdoor_integration: bool | None = None,
        sensitivity: str | None = None,
    ) -> None:
        """Enable Pure Boost Configuration."""

        params: dict[str, str | bool] = {
            "enabled": True,
        }
        if sensitivity is not None:
            params["sensitivity"] = sensitivity[0].upper()
        if indoor_integration is not None:
            params["measurementsIntegration"] = indoor_integration
        if ac_integration is not None:
            params["acIntegration"] = ac_integration
        if geo_integration is not None:
            params["geoIntegration"] = geo_integration
        if outdoor_integration is not None:
            params["primeIntegration"] = outdoor_integration

        await self.api_call_custom_service_pure_boost(
            key="pure_boost_enabled",
            value=True,
            data=params,
        )

    async def async_enable_climate_react(
        self,
        high_temperature_threshold: float,
        high_temperature_state: dict[str, Any],
        low_temperature_threshold: float,
        low_temperature_state: dict[str, Any],
        smart_type: str,
    ) -> None:
        """Enable Climate React Configuration."""
        high_temp = high_temperature_threshold
        low_temp = low_temperature_threshold

        if high_temperature_state.get("temperatureUnit") == "F":
            high_temp = TemperatureConverter.convert(
                high_temperature_threshold,
                UnitOfTemperature.FAHRENHEIT,
                UnitOfTemperature.CELSIUS,
            )
            low_temp = TemperatureConverter.convert(
                low_temperature_threshold,
                UnitOfTemperature.FAHRENHEIT,
                UnitOfTemperature.CELSIUS,
            )

        if smart_type == "feelslike":
            smart_type = "feelsLike"

        params: dict[str, str | bool | float | dict] = {
            "enabled": True,
            "deviceUid": self._device_id,
            "highTemperatureState": high_temperature_state,
            "highTemperatureThreshold": high_temp,
            "lowTemperatureState": low_temperature_state,
            "lowTemperatureThreshold": low_temp,
            "type": smart_type,
        }

        await self.api_call_custom_service_climate_react(
            key="smart_on",
            value=True,
            data=params,
        )

    @async_handle_api_call
    async def async_send_api_call(
        self,
        key: str,
        value: Any,
        name: str,
        assumed_state: bool = False,
        transformation: dict | None = None,
    ) -> bool:
        """Make service call to api."""
        if transformation:
            value = transformation[value]
        result = await self._client.async_set_ac_state_property(
            self._device_id,
            name,
            value,
            self.device_data.ac_states,
            assumed_state,
        )
        return bool(result.get("result", {}).get("status") == "Success")

    @async_handle_api_call
    async def api_call_custom_service_timer(
        self,
        key: str,
        value: Any,
        data: dict,
    ) -> bool:
        """Make service call to api."""
        result = await self._client.async_set_timer(self._device_id, data)
        return bool(result.get("status") == "success")

    @async_handle_api_call
    async def api_call_custom_service_pure_boost(
        self,
        key: str,
        value: Any,
        data: dict,
    ) -> bool:
        """Make service call to api."""
        result = await self._client.async_set_pureboost(self._device_id, data)
        return bool(result.get("status") == "success")

    @async_handle_api_call
    async def api_call_custom_service_climate_react(
        self,
        key: str,
        value: Any,
        data: dict,
    ) -> bool:
        """Make service call to api."""
        result = await self._client.async_set_climate_react(self._device_id, data)
        return bool(result.get("status") == "success")

    @async_handle_api_call
    async def api_call_custom_service_full_ac_state(
        self,
        key: str,
        value: Any,
        data: dict,
    ) -> bool:
        """Make service call to api."""
        result = await self._client.async_set_ac_states(self._device_id, data)
        return bool(result.get("result", {}).get("status") == "Success")
