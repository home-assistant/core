"""Support for Tuya Climate."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.climate import (
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import IntegerTypeData, TuyaEntity
from .const import DOMAIN, LOGGER, TUYA_DISCOVERY_NEW, DPCode, DPType

TUYA_HVAC_TO_HA = {
    "auto": HVACMode.HEAT_COOL,
    "cold": HVACMode.COOL,
    "freeze": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "hot": HVACMode.HEAT,
    "manual": HVACMode.HEAT_COOL,
    "wet": HVACMode.DRY,
    "wind": HVACMode.FAN_ONLY,
}


@dataclass
class TuyaClimateSensorDescriptionMixin:
    """Define an entity description mixin for climate entities."""

    switch_only_hvac_mode: HVACMode


@dataclass
class TuyaClimateEntityDescription(
    ClimateEntityDescription, TuyaClimateSensorDescriptionMixin
):
    """Describe an Tuya climate entity."""


CLIMATE_DESCRIPTIONS: dict[str, TuyaClimateEntityDescription] = {
    # Air conditioner
    # https://developer.tuya.com/en/docs/iot/categorykt?id=Kaiuz0z71ov2n
    "kt": TuyaClimateEntityDescription(
        key="kt",
        switch_only_hvac_mode=HVACMode.COOL,
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf46epy4j82
    "qn": TuyaClimateEntityDescription(
        key="qn",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    # Heater
    # https://developer.tuya.com/en/docs/iot/categoryrs?id=Kaiuz0nfferyx
    "rs": TuyaClimateEntityDescription(
        key="rs",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
    # Thermostat
    # https://developer.tuya.com/en/docs/iot/f?id=K9gf45ld5l0t9
    "wk": TuyaClimateEntityDescription(
        key="wk",
        switch_only_hvac_mode=HVACMode.HEAT_COOL,
    ),
    # Thermostatic Radiator Valve
    # Not documented
    "wkf": TuyaClimateEntityDescription(
        key="wkf",
        switch_only_hvac_mode=HVACMode.HEAT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya climate dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya climate."""
        entities: list[TuyaClimateEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if device and device.category in CLIMATE_DESCRIPTIONS:
                entities.append(
                    TuyaClimateEntity(
                        device,
                        hass_data.device_manager,
                        CLIMATE_DESCRIPTIONS[device.category],
                    )
                )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaClimateEntity(TuyaEntity, ClimateEntity):
    """Tuya Climate Device."""

    _current_humidity: IntegerTypeData | None = None
    _current_temperature: IntegerTypeData | None = None
    _hvac_to_tuya: dict[str, str]
    _set_humidity: IntegerTypeData | None = None
    _set_temperature: IntegerTypeData | None = None
    entity_description: TuyaClimateEntityDescription

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaClimateEntityDescription,
    ) -> None:
        """Determine which values to use."""
        self._attr_target_temperature_step = 1.0
        self._attr_supported_features = 0
        self.entity_description = description

        super().__init__(device, device_manager)

        # If both temperature values for celsius and fahrenheit are present,
        # use whatever the device is set to, with a fallback to celsius.
        prefered_temperature_unit = TEMP_CELSIUS
        if all(
            dpcode in device.status
            for dpcode in (DPCode.TEMP_CURRENT, DPCode.TEMP_CURRENT_F)
        ) or all(
            dpcode in device.status for dpcode in (DPCode.TEMP_SET, DPCode.TEMP_SET_F)
        ):
            prefered_temperature_unit = TEMP_CELSIUS
            if any(
                "f" in device.status[dpcode].lower()
                for dpcode in (DPCode.C_F, DPCode.TEMP_UNIT_CONVERT)
                if isinstance(device.status.get(dpcode), str)
            ):
                prefered_temperature_unit = TEMP_FAHRENHEIT

        # Default to Celsius
        self._attr_temperature_unit = TEMP_CELSIUS

        # Figure out current temperature, use preferred unit or what is available
        celsius_type = self.find_dpcode(
            (DPCode.TEMP_CURRENT, DPCode.UPPER_TEMP), dptype=DPType.INTEGER
        )
        farhenheit_type = self.find_dpcode(
            (DPCode.TEMP_CURRENT_F, DPCode.UPPER_TEMP_F), dptype=DPType.INTEGER
        )
        if farhenheit_type and (
            prefered_temperature_unit == TEMP_FAHRENHEIT
            or (prefered_temperature_unit == TEMP_CELSIUS and not celsius_type)
        ):
            self._attr_temperature_unit = TEMP_FAHRENHEIT
            self._current_temperature = farhenheit_type
        elif celsius_type:
            self._attr_temperature_unit = TEMP_CELSIUS
            self._current_temperature = celsius_type

        # Figure out setting temperature, use preferred unit or what is available
        celsius_type = self.find_dpcode(
            DPCode.TEMP_SET, dptype=DPType.INTEGER, prefer_function=True
        )
        farhenheit_type = self.find_dpcode(
            DPCode.TEMP_SET_F, dptype=DPType.INTEGER, prefer_function=True
        )
        if farhenheit_type and (
            prefered_temperature_unit == TEMP_FAHRENHEIT
            or (prefered_temperature_unit == TEMP_CELSIUS and not celsius_type)
        ):
            self._set_temperature = farhenheit_type
        elif celsius_type:
            self._set_temperature = celsius_type

        # Get integer type data for the dpcode to set temperature, use
        # it to define min, max & step temperatures
        if self._set_temperature:
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_max_temp = self._set_temperature.max_scaled
            self._attr_min_temp = self._set_temperature.min_scaled
            self._attr_target_temperature_step = self._set_temperature.step_scaled

        # Determine HVAC modes
        self._attr_hvac_modes: list[str] = []
        self._hvac_to_tuya = {}
        if enum_type := self.find_dpcode(
            DPCode.MODE, dptype=DPType.ENUM, prefer_function=True
        ):
            self._attr_hvac_modes = [HVACMode.OFF]
            for tuya_mode, ha_mode in TUYA_HVAC_TO_HA.items():
                if tuya_mode in enum_type.range:
                    self._hvac_to_tuya[ha_mode] = tuya_mode
                    self._attr_hvac_modes.append(ha_mode)
        elif self.find_dpcode(DPCode.SWITCH, prefer_function=True):
            self._attr_hvac_modes = [
                HVACMode.OFF,
                description.switch_only_hvac_mode,
            ]

        # Determine dpcode to use for setting the humidity
        if int_type := self.find_dpcode(
            DPCode.HUMIDITY_SET, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY
            self._set_humidity = int_type
            self._attr_min_humidity = int(int_type.min_scaled)
            self._attr_max_humidity = int(int_type.max_scaled)

        # Determine dpcode to use for getting the current humidity
        self._current_humidity = self.find_dpcode(
            DPCode.HUMIDITY_CURRENT, dptype=DPType.INTEGER
        )

        # Determine fan modes
        if enum_type := self.find_dpcode(
            (DPCode.FAN_SPEED_ENUM, DPCode.WINDSPEED),
            dptype=DPType.ENUM,
            prefer_function=True,
        ):
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = enum_type.range

        # Determine swing modes
        if self.find_dpcode(
            (
                DPCode.SHAKE,
                DPCode.SWING,
                DPCode.SWITCH_HORIZONTAL,
                DPCode.SWITCH_VERTICAL,
            ),
            prefer_function=True,
        ):
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            self._attr_swing_modes = [SWING_OFF]
            if self.find_dpcode((DPCode.SHAKE, DPCode.SWING), prefer_function=True):
                self._attr_swing_modes.append(SWING_ON)

            if self.find_dpcode(DPCode.SWITCH_HORIZONTAL, prefer_function=True):
                self._attr_swing_modes.append(SWING_HORIZONTAL)

            if self.find_dpcode(DPCode.SWITCH_VERTICAL, prefer_function=True):
                self._attr_swing_modes.append(SWING_VERTICAL)

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()

        # Log unknown modes
        if enum_type := self.find_dpcode(
            DPCode.MODE, dptype=DPType.ENUM, prefer_function=True
        ):
            for tuya_mode in enum_type.range:
                if tuya_mode not in TUYA_HVAC_TO_HA:
                    LOGGER.warning(
                        "Unknown HVAC mode '%s' for device %s; assuming it as off",
                        tuya_mode,
                        self.device.name,
                    )

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        commands = [{"code": DPCode.SWITCH, "value": hvac_mode != HVACMode.OFF}]
        if hvac_mode in self._hvac_to_tuya:
            commands.append(
                {"code": DPCode.MODE, "value": self._hvac_to_tuya[hvac_mode]}
            )
        self._send_command(commands)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self._send_command([{"code": DPCode.FAN_SPEED_ENUM, "value": fan_mode}])

    def set_humidity(self, humidity: float) -> None:
        """Set new target humidity."""
        if self._set_humidity is None:
            raise RuntimeError(
                "Cannot set humidity, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self._set_humidity.dpcode,
                    "value": self._set_humidity.scale_value_back(humidity),
                }
            ]
        )

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        # The API accepts these all at once and will ignore the codes
        # that don't apply to the device being controlled.
        self._send_command(
            [
                {
                    "code": DPCode.SHAKE,
                    "value": swing_mode == SWING_ON,
                },
                {
                    "code": DPCode.SWING,
                    "value": swing_mode == SWING_ON,
                },
                {
                    "code": DPCode.SWITCH_VERTICAL,
                    "value": swing_mode in (SWING_BOTH, SWING_VERTICAL),
                },
                {
                    "code": DPCode.SWITCH_HORIZONTAL,
                    "value": swing_mode in (SWING_BOTH, SWING_HORIZONTAL),
                },
            ]
        )

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if self._set_temperature is None:
            raise RuntimeError(
                "Cannot set target temperature, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self._set_temperature.dpcode,
                    "value": round(
                        self._set_temperature.scale_value_back(kwargs["temperature"])
                    ),
                }
            ]
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self._current_temperature is None:
            return None

        temperature = self.device.status.get(self._current_temperature.dpcode)
        if temperature is None:
            return None

        if self._current_temperature.scale == 0 and self._current_temperature.step != 1:
            # The current temperature can have a scale of 0 or 1 and is used for
            # rounding, Home Assistant doesn't need to round but we will always
            # need to divide the value by 10^1 in case of 0 as scale.
            # https://developer.tuya.com/en/docs/iot/shift-temperature-scale-follow-the-setting-of-app-account-center?id=Ka9qo7so58efq#title-7-Round%20values
            temperature = temperature / 10

        return self._current_temperature.scale_value(temperature)

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        if self._current_humidity is None:
            return None

        humidity = self.device.status.get(self._current_humidity.dpcode)
        if humidity is None:
            return None

        return round(self._current_humidity.scale_value(humidity))

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        if self._set_temperature is None:
            return None

        temperature = self.device.status.get(self._set_temperature.dpcode)
        if temperature is None:
            return None

        return self._set_temperature.scale_value(temperature)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity currently set to be reached."""
        if self._set_humidity is None:
            return None

        humidity = self.device.status.get(self._set_humidity.dpcode)
        if humidity is None:
            return None

        return round(self._set_humidity.scale_value(humidity))

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac mode."""
        # If the switch off, hvac mode is off as well. Unless the switch
        # the switch is on or doesn't exists of course...
        if not self.device.status.get(DPCode.SWITCH, True):
            return HVACMode.OFF

        if DPCode.MODE not in self.device.function:
            if self.device.status.get(DPCode.SWITCH, False):
                return self.entity_description.switch_only_hvac_mode
            return HVACMode.OFF

        if (
            mode := self.device.status.get(DPCode.MODE)
        ) is not None and mode in TUYA_HVAC_TO_HA:
            return TUYA_HVAC_TO_HA[mode]

        return HVACMode.OFF

    @property
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        return self.device.status.get(DPCode.FAN_SPEED_ENUM)

    @property
    def swing_mode(self) -> str:
        """Return swing mode."""
        if any(
            self.device.status.get(dpcode) for dpcode in (DPCode.SHAKE, DPCode.SWING)
        ):
            return SWING_ON

        horizontal = self.device.status.get(DPCode.SWITCH_HORIZONTAL)
        vertical = self.device.status.get(DPCode.SWITCH_VERTICAL)
        if horizontal and vertical:
            return SWING_BOTH
        if horizontal:
            return SWING_HORIZONTAL
        if vertical:
            return SWING_VERTICAL

        return SWING_OFF

    def turn_on(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        if DPCode.SWITCH in self.device.function:
            self._send_command([{"code": DPCode.SWITCH, "value": True}])
            return

        # Fake turn on
        for mode in (HVACMode.HEAT_COOL, HVACMode.HEAT, HVACMode.COOL):
            if mode not in self.hvac_modes:
                continue
            self.set_hvac_mode(mode)
            break

    def turn_off(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        if DPCode.SWITCH in self.device.function:
            self._send_command([{"code": DPCode.SWITCH, "value": False}])
            return

        # Fake turn off
        if HVACMode.OFF in self.hvac_modes:
            self.set_hvac_mode(HVACMode.OFF)
