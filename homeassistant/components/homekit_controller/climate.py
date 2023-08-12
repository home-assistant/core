"""Support for Homekit climate devices."""
from __future__ import annotations

import logging
from typing import Any, Final

from aiohomekit.model.characteristics import (
    ActivationStateValues,
    CharacteristicsTypes,
    CurrentHeaterCoolerStateValues,
    HeatingCoolingCurrentValues,
    HeatingCoolingTargetValues,
    SwingModeValues,
    TargetHeaterCoolerStateValues,
)
from aiohomekit.model.services import Service, ServicesTypes
from aiohomekit.utils import clamp_enum_to_char

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_HIGH,
    FAN_OFF,
    FAN_ON,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage
)


from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import HomeKitEntity

_LOGGER = logging.getLogger(__name__)

# Map of Homekit operation modes to hass modes
MODE_HOMEKIT_TO_HASS = {
    HeatingCoolingTargetValues.OFF: HVACMode.OFF,
    HeatingCoolingTargetValues.HEAT: HVACMode.HEAT,
    HeatingCoolingTargetValues.COOL: HVACMode.COOL,
    HeatingCoolingTargetValues.AUTO: HVACMode.HEAT_COOL,
}

CURRENT_MODE_HOMEKIT_TO_HASS = {
    HeatingCoolingCurrentValues.IDLE: HVACAction.IDLE,
    HeatingCoolingCurrentValues.HEATING: HVACAction.HEATING,
    HeatingCoolingCurrentValues.COOLING: HVACAction.COOLING,
}

SWING_MODE_HOMEKIT_TO_HASS = {
    SwingModeValues.DISABLED: SWING_OFF,
    SwingModeValues.ENABLED: SWING_VERTICAL,
}

CURRENT_HEATER_COOLER_STATE_HOMEKIT_TO_HASS = {
    CurrentHeaterCoolerStateValues.INACTIVE: HVACAction.OFF,
    CurrentHeaterCoolerStateValues.IDLE: HVACAction.IDLE,
    CurrentHeaterCoolerStateValues.HEATING: HVACAction.HEATING,
    CurrentHeaterCoolerStateValues.COOLING: HVACAction.COOLING,
}

TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS = {
    TargetHeaterCoolerStateValues.AUTOMATIC: HVACMode.HEAT_COOL,
    TargetHeaterCoolerStateValues.HEAT: HVACMode.HEAT,
    TargetHeaterCoolerStateValues.COOL: HVACMode.COOL,
}


# Map of hass operation modes to homekit modes
MODE_HASS_TO_HOMEKIT = {v: k for k, v in MODE_HOMEKIT_TO_HASS.items()}

TARGET_HEATER_COOLER_STATE_HASS_TO_HOMEKIT = {
    v: k for k, v in TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS.items()
}

SWING_MODE_HASS_TO_HOMEKIT = {v: k for k, v in SWING_MODE_HOMEKIT_TO_HASS.items()}

DEFAULT_MIN_STEP: Final = 1.0

ROTATION_SPEED_LOW = 33
ROTATION_SPEED_MEDIUM = 66
ROTATION_SPEED_HIGH = 100


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit climate."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if not (entity_class := ENTITY_TYPES.get(service.type)):
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        entity: HomeKitEntity = entity_class(conn, info)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.CLIMATE
        )
        async_add_entities([entity])
        return True

    conn.add_listener(async_add_service)


class HomeKitBaseClimateEntity(HomeKitEntity, ClimateEntity):
    """The base HomeKit Controller climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.TEMPERATURE_CURRENT,
            CharacteristicsTypes.FAN_STATE_TARGET,
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.service.value(CharacteristicsTypes.TEMPERATURE_CURRENT)

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the available fan modes."""
        if self.service.has(CharacteristicsTypes.FAN_STATE_TARGET):
            return [FAN_ON, FAN_AUTO]
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_mode = self.service.value(CharacteristicsTypes.FAN_STATE_TARGET)
        return FAN_AUTO if fan_mode else FAN_ON

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Turn fan to manual/auto."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.FAN_STATE_TARGET: int(fan_mode == FAN_AUTO)}
        )

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = ClimateEntityFeature(0)

        if self.service.has(CharacteristicsTypes.FAN_STATE_TARGET):
            features |= ClimateEntityFeature.FAN_MODE

        return features


class HomeKitHeaterCoolerEntity(HomeKitBaseClimateEntity):
    """Representation of a Homekit climate device."""

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return super().get_characteristic_types() + [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.CURRENT_HEATER_COOLER_STATE,
            CharacteristicsTypes.TARGET_HEATER_COOLER_STATE,
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD,
            CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD,
            CharacteristicsTypes.SWING_MODE,
            CharacteristicsTypes.ROTATION_SPEED,
        ]

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the available fan modes."""
        if self.service.has(CharacteristicsTypes.ROTATION_SPEED):
            return [FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        speed_range = [self.service[CharacteristicsTypes.ROTATION_SPEED].minValue,
                       self.service[CharacteristicsTypes.ROTATION_SPEED].maxValue]
        speed_percentage = ranged_value_to_percentage(
            speed_range, self.service.value(
                CharacteristicsTypes.ROTATION_SPEED)
        )
        fan_mode = FAN_OFF

        # homekit value 0 33 66 100
        if speed_percentage > ROTATION_SPEED_MEDIUM:
            fan_mode = FAN_HIGH
        elif speed_percentage > ROTATION_SPEED_LOW:
            fan_mode = FAN_MEDIUM
        elif speed_percentage > 0:
            fan_mode = FAN_LOW

        return fan_mode

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        rotation = 0
        if fan_mode == FAN_LOW:
            rotation = ROTATION_SPEED_LOW
        elif fan_mode == FAN_MEDIUM:
            rotation = ROTATION_SPEED_MEDIUM
        elif fan_mode == FAN_HIGH:
            rotation = ROTATION_SPEED_HIGH

        speed_range = [self.service[CharacteristicsTypes.ROTATION_SPEED].minValue,
                       self.service[CharacteristicsTypes.ROTATION_SPEED].maxValue]
        speed = round(
            percentage_to_ranged_value(speed_range, rotation)
        )
        await self.async_put_characteristics(
            {CharacteristicsTypes.ROTATION_SPEED: speed}
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL:
            await self.async_put_characteristics(
                {CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD: temp}
            )
        elif state == TargetHeaterCoolerStateValues.HEAT:
            await self.async_put_characteristics(
                {CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD: temp}
            )
        else:
            hvac_mode = TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS.get(state)
            _LOGGER.warning(
                (
                    "HomeKit device %s: Setting temperature in %s mode is not supported"
                    " yet; Consider raising a ticket if you have this device and want"
                    " to help us implement this feature"
                ),
                self.entity_id,
                hvac_mode,
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_put_characteristics(
                {CharacteristicsTypes.ACTIVE: ActivationStateValues.INACTIVE}
            )
            return
        if hvac_mode not in {HVACMode.HEAT, HVACMode.COOL}:
            _LOGGER.warning(
                (
                    "HomeKit device %s: Setting temperature in %s mode is not supported"
                    " yet; Consider raising a ticket if you have this device and want"
                    " to help us implement this feature"
                ),
                self.entity_id,
                hvac_mode,
            )
        await self.async_put_characteristics(
            {
                CharacteristicsTypes.ACTIVE: ActivationStateValues.ACTIVE,
                CharacteristicsTypes.TARGET_HEATER_COOLER_STATE: TARGET_HEATER_COOLER_STATE_HASS_TO_HOMEKIT[
                    hvac_mode
                ],
            }
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL:
            return self.service.value(
                CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
            )
        if state == TargetHeaterCoolerStateValues.HEAT:
            return self.service.value(
                CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
            )
        return None

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL and self.service.has(
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
        ):
            return (
                self.service[CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD].minStep
                or DEFAULT_MIN_STEP
            )
        if state == TargetHeaterCoolerStateValues.HEAT and self.service.has(
            CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
        ):
            return (
                self.service[CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD].minStep
                or DEFAULT_MIN_STEP
            )
        return DEFAULT_MIN_STEP

    @property
    def min_temp(self) -> float:
        """Return the minimum target temp."""
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL and self.service.has(
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
        ):
            return (
                self.service[
                    CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
                ].minValue
                or DEFAULT_MIN_TEMP
            )
        if state == TargetHeaterCoolerStateValues.HEAT and self.service.has(
            CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
        ):
            return (
                self.service[
                    CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
                ].minValue
                or DEFAULT_MIN_TEMP
            )
        return super().min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum target temp."""
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL and self.service.has(
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
        ):
            return (
                self.service[
                    CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
                ].maxValue
                or DEFAULT_MAX_TEMP
            )
        if state == TargetHeaterCoolerStateValues.HEAT and self.service.has(
            CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
        ):
            return (
                self.service[
                    CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
                ].maxValue
                or DEFAULT_MAX_TEMP
            )
        return super().max_temp

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        # This characteristic describes the current mode of a device,
        # e.g. a thermostat is "heating" a room to 75 degrees Fahrenheit.
        # Can be 0 - 3 (Off, Idle, Heat, Cool)
        if (
            self.service.value(CharacteristicsTypes.ACTIVE)
            == ActivationStateValues.INACTIVE
        ):
            return HVACAction.OFF
        value = self.service.value(CharacteristicsTypes.CURRENT_HEATER_COOLER_STATE)
        return CURRENT_HEATER_COOLER_STATE_HOMEKIT_TO_HASS.get(value)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        # This characteristic describes the target mode
        # E.g. should the device start heating a room if the temperature
        # falls below the target temperature.
        # Can be 0 - 2 (Auto, Heat, Cool)
        if (
            self.service.value(CharacteristicsTypes.ACTIVE)
            == ActivationStateValues.INACTIVE
        ):
            return HVACMode.OFF
        value = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        return TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS[value]

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        valid_values = clamp_enum_to_char(
            TargetHeaterCoolerStateValues,
            self.service[CharacteristicsTypes.TARGET_HEATER_COOLER_STATE],
        )
        modes = [
            TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS[mode] for mode in valid_values
        ]
        modes.append(HVACMode.OFF)
        return modes

    @property
    def swing_mode(self) -> str:
        """Return the swing setting.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        value = self.service.value(CharacteristicsTypes.SWING_MODE)
        return SWING_MODE_HOMEKIT_TO_HASS[value]

    @property
    def swing_modes(self) -> list[str]:
        """Return the list of available swing modes.

        Requires ClimateEntityFeature.SWING_MODE.
        """
        valid_values = clamp_enum_to_char(
            SwingModeValues,
            self.service[CharacteristicsTypes.SWING_MODE],
        )
        return [SWING_MODE_HOMEKIT_TO_HASS[mode] for mode in valid_values]

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.SWING_MODE: SWING_MODE_HASS_TO_HOMEKIT[swing_mode]}
        )

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = super().supported_features

        if self.service.has(CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD):
            features |= ClimateEntityFeature.TARGET_TEMPERATURE

        if self.service.has(CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD):
            features |= ClimateEntityFeature.TARGET_TEMPERATURE

        if self.service.has(CharacteristicsTypes.SWING_MODE):
            features |= ClimateEntityFeature.SWING_MODE

        if self.service.has(CharacteristicsTypes.ROTATION_SPEED):
            features |= ClimateEntityFeature.FAN_MODE

        return features


class HomeKitClimateEntity(HomeKitBaseClimateEntity):
    """Representation of a Homekit climate device."""

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return super().get_characteristic_types() + [
            CharacteristicsTypes.HEATING_COOLING_CURRENT,
            CharacteristicsTypes.HEATING_COOLING_TARGET,
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD,
            CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD,
            CharacteristicsTypes.TEMPERATURE_TARGET,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
            CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET,
        ]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        chars: dict[str, Any] = {}

        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_TARGET)
        mode = MODE_HOMEKIT_TO_HASS[value]

        if kwargs.get(ATTR_HVAC_MODE, mode) != mode:
            mode = kwargs[ATTR_HVAC_MODE]
            chars[CharacteristicsTypes.HEATING_COOLING_TARGET] = MODE_HASS_TO_HOMEKIT[
                mode
            ]

        temp = kwargs.get(ATTR_TEMPERATURE)
        heat_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        cool_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if (
            (mode == HVACMode.HEAT_COOL)
            and (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE & self.supported_features
            )
            and heat_temp
            and cool_temp
        ):
            if temp is None:
                temp = (cool_temp + heat_temp) / 2
            chars.update(
                {
                    CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD: heat_temp,
                    CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD: cool_temp,
                    CharacteristicsTypes.TEMPERATURE_TARGET: temp,
                }
            )
        else:
            chars[CharacteristicsTypes.TEMPERATURE_TARGET] = temp

        await self.async_put_characteristics(chars)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET: humidity}
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        await self.async_put_characteristics(
            {
                CharacteristicsTypes.HEATING_COOLING_TARGET: MODE_HASS_TO_HOMEKIT[
                    hvac_mode
                ],
            }
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_TARGET)
        if (MODE_HOMEKIT_TO_HASS.get(value) in {HVACMode.HEAT, HVACMode.COOL}) or (
            (MODE_HOMEKIT_TO_HASS.get(value) in {HVACMode.HEAT_COOL})
            and not (
                ClimateEntityFeature.TARGET_TEMPERATURE_RANGE & self.supported_features
            )
        ):
            return self.service.value(CharacteristicsTypes.TEMPERATURE_TARGET)
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_TARGET)
        if (MODE_HOMEKIT_TO_HASS.get(value) in {HVACMode.HEAT_COOL}) and (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE & self.supported_features
        ):
            return self.service.value(
                CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
            )
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_TARGET)
        if (MODE_HOMEKIT_TO_HASS.get(value) in {HVACMode.HEAT_COOL}) and (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE & self.supported_features
        ):
            return self.service.value(
                CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
            )
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum target temp."""
        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_TARGET)
        if (MODE_HOMEKIT_TO_HASS.get(value) in {HVACMode.HEAT_COOL}) and (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE & self.supported_features
        ):
            min_temp = self.service[
                CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
            ].minValue
            if min_temp is not None:
                return min_temp
        elif MODE_HOMEKIT_TO_HASS.get(value) in {
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
        }:
            min_temp = self.service[CharacteristicsTypes.TEMPERATURE_TARGET].minValue
            if min_temp is not None:
                return min_temp
        return super().min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum target temp."""
        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_TARGET)
        if (MODE_HOMEKIT_TO_HASS.get(value) in {HVACMode.HEAT_COOL}) and (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE & self.supported_features
        ):
            max_temp = self.service[
                CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
            ].maxValue
            if max_temp is not None:
                return max_temp
        elif MODE_HOMEKIT_TO_HASS.get(value) in {
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
        }:
            max_temp = self.service[CharacteristicsTypes.TEMPERATURE_TARGET].maxValue
            if max_temp is not None:
                return max_temp
        return super().max_temp

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)

    @property
    def target_humidity(self) -> int:
        """Return the humidity we try to reach."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET)

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        min_humidity = self.service[
            CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET
        ].minValue
        if min_humidity is not None:
            return int(min_humidity)
        return super().min_humidity

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        max_humidity = self.service[
            CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET
        ].maxValue
        if max_humidity is not None:
            return int(max_humidity)
        return super().max_humidity

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        # This characteristic describes the current mode of a device,
        # e.g. a thermostat is "heating" a room to 75 degrees Fahrenheit.
        # Can be 0 - 2 (Off, Heat, Cool)

        # If the HVAC is switched off, it must be idle
        # This works around a bug in some devices (like Eve radiator valves) that
        # return they are heating when they are not.
        target = self.service.value(CharacteristicsTypes.HEATING_COOLING_TARGET)
        if target == HeatingCoolingTargetValues.OFF:
            return HVACAction.IDLE

        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_CURRENT)
        return CURRENT_MODE_HOMEKIT_TO_HASS.get(value)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        # This characteristic describes the target mode
        # E.g. should the device start heating a room if the temperature
        # falls below the target temperature.
        # Can be 0 - 3 (Off, Heat, Cool, Auto)
        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_TARGET)
        return MODE_HOMEKIT_TO_HASS[value]

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        valid_values = clamp_enum_to_char(
            HeatingCoolingTargetValues,
            self.service[CharacteristicsTypes.HEATING_COOLING_TARGET],
        )
        return [MODE_HOMEKIT_TO_HASS[mode] for mode in valid_values]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = super().supported_features

        if self.service.has(CharacteristicsTypes.TEMPERATURE_TARGET):
            features |= ClimateEntityFeature.TARGET_TEMPERATURE

        if self.service.has(
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
        ) and self.service.has(CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD):
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

        if self.service.has(CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET):
            features |= ClimateEntityFeature.TARGET_HUMIDITY

        return features


ENTITY_TYPES = {
    ServicesTypes.HEATER_COOLER: HomeKitHeaterCoolerEntity,
    ServicesTypes.THERMOSTAT: HomeKitClimateEntity,
}
