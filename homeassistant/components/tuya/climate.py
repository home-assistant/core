"""Support for Tuya Climate."""
from __future__ import annotations

from dataclasses import dataclass
import functools as ft
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
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import IntegerTypeData, TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType

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

CATEGORY_INFRARED_AC = "infrared_ac"


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
    CATEGORY_INFRARED_AC: TuyaClimateEntityDescription(
        key=CATEGORY_INFRARED_AC, switch_only_hvac_mode=HVACMode.HEAT_COOL
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
        entities: list[ClimateEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if device and device.category in CLIMATE_DESCRIPTIONS:
                entity: ClimateEntity
                if device.category == CATEGORY_INFRARED_AC:
                    entity = TuyaInfraredClimateEntity(
                        device,
                        hass_data.device_manager,
                        CLIMATE_DESCRIPTIONS[device.category],
                    )
                else:
                    entity = TuyaClimateEntity(
                        device,
                        hass_data.device_manager,
                        CLIMATE_DESCRIPTIONS[device.category],
                    )
                entities.append(entity)
        async_add_entities(entities)

    await TuyaInfraredClimateEntity.async_fixup_device_status(
        hass, hass_data, [*hass_data.device_manager.device_map]
    )
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
        self.entity_description = description

        super().__init__(device, device_manager)

        # If both temperature values for celsius and fahrenheit are present,
        # use whatever the device is set to, with a fallback to celsius.
        prefered_temperature_unit = None
        if all(
            dpcode in device.status
            for dpcode in (DPCode.TEMP_CURRENT, DPCode.TEMP_CURRENT_F)
        ) or all(
            dpcode in device.status for dpcode in (DPCode.TEMP_SET, DPCode.TEMP_SET_F)
        ):
            prefered_temperature_unit = UnitOfTemperature.CELSIUS
            if any(
                "f" in device.status[dpcode].lower()
                for dpcode in (DPCode.C_F, DPCode.TEMP_UNIT_CONVERT)
                if isinstance(device.status.get(dpcode), str)
            ):
                prefered_temperature_unit = UnitOfTemperature.FAHRENHEIT

        # Default to Celsius
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        # Figure out current temperature, use preferred unit or what is available
        celsius_type = self.find_dpcode(
            (DPCode.TEMP_CURRENT, DPCode.UPPER_TEMP), dptype=DPType.INTEGER
        )
        farhenheit_type = self.find_dpcode(
            (DPCode.TEMP_CURRENT_F, DPCode.UPPER_TEMP_F), dptype=DPType.INTEGER
        )
        if farhenheit_type and (
            prefered_temperature_unit == UnitOfTemperature.FAHRENHEIT
            or (
                prefered_temperature_unit == UnitOfTemperature.CELSIUS
                and not celsius_type
            )
        ):
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
            self._current_temperature = farhenheit_type
        elif celsius_type:
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._current_temperature = celsius_type

        # Figure out setting temperature, use preferred unit or what is available
        celsius_type = self.find_dpcode(
            DPCode.TEMP_SET, dptype=DPType.INTEGER, prefer_function=True
        )
        farhenheit_type = self.find_dpcode(
            DPCode.TEMP_SET_F, dptype=DPType.INTEGER, prefer_function=True
        )
        if farhenheit_type and (
            prefered_temperature_unit == UnitOfTemperature.FAHRENHEIT
            or (
                prefered_temperature_unit == UnitOfTemperature.CELSIUS
                and not celsius_type
            )
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
            unknown_hvac_modes: list[str] = []
            for tuya_mode in enum_type.range:
                if tuya_mode in TUYA_HVAC_TO_HA:
                    ha_mode = TUYA_HVAC_TO_HA[tuya_mode]
                    self._hvac_to_tuya[ha_mode] = tuya_mode
                    self._attr_hvac_modes.append(ha_mode)
                else:
                    unknown_hvac_modes.append(tuya_mode)

            if unknown_hvac_modes:  # Tuya modes are presets instead of hvac_modes
                self._attr_hvac_modes.append(description.switch_only_hvac_mode)
                self._attr_preset_modes = unknown_hvac_modes
                self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
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

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        commands = [{"code": DPCode.SWITCH, "value": hvac_mode != HVACMode.OFF}]
        if hvac_mode in self._hvac_to_tuya:
            commands.append(
                {"code": DPCode.MODE, "value": self._hvac_to_tuya[hvac_mode]}
            )
        self._send_command(commands)

    def set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        commands = [{"code": DPCode.MODE, "value": preset_mode}]
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
                "Cannot set target temperature, device doesn't provide methods to"
                " set it"
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

        # If the switch is on, and the mode does not match any hvac mode.
        if self.device.status.get(DPCode.SWITCH, False):
            return self.entity_description.switch_only_hvac_mode

        return HVACMode.OFF

    @property
    def preset_mode(self) -> str | None:
        """Return preset mode."""
        if DPCode.MODE not in self.device.function:
            return None

        mode = self.device.status.get(DPCode.MODE)
        if mode in TUYA_HVAC_TO_HA:
            return None

        return mode

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


class TuyaInfraredClimateEntity(TuyaEntity, ClimateEntity):
    """Tuya Climate Device."""

    entity_description: TuyaClimateEntityDescription
    _attr_min_temp: int = 16
    _attr_max_temp: int = 24
    _attr_target_temperature_step: float = 1.0
    _attr_temparature: int
    _attr_current_temperature: int = 30
    sensor_device: TuyaDevice = None

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: TuyaClimateEntityDescription,
    ) -> None:
        """Determine which values to use."""
        self.entity_description = description

        super().__init__(device, device_manager)

        device_list = [*device_manager.device_manager.device_map]
        for device_id in device_list:
            sensor_device = device_manager.device_map[device_id]
            if (
                sensor_device.category == "wnykq"
                and sensor_device.local_key == device.local_key
            ):
                self.sensor_device = sensor_device

        self._attr_should_poll = True

        # Default to Celsius
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.AUTO,
        ]
        self._attr_supported_features |= (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        self._attr_fan_modes = [
            "auto",
            "low",
            "middle",
            "high",
        ]

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if self.is_ready():
            new_temp = kwargs["temperature"]
            self._send_command(
                [
                    {
                        "code": DPCode.TEMP,
                        "value": round(new_temp),
                    }
                ]
            )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        if self.is_ready():
            return float(self.device.status.get(DPCode.TEMP))
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac mode."""
        # If the switch off, hvac mode is off as well. Unless the switch
        # the switch is on or doesn't exists of course...
        if self.is_ready():
            power = self.device.status.get(DPCode.POWER, "0")
            if "0" == power:
                return HVACMode.OFF

            mode = self.device.status.get(DPCode.MODE, "1")
            # pylint: disable=no-else-return
            if "0" == mode:
                return HVACMode.COOL
            elif "1" == mode:
                return HVACMode.HEAT
            elif "2" == mode:
                return HVACMode.AUTO
        return HVACMode.OFF

    def is_ready(self) -> bool:
        """Return true if status initialized properly."""
        status = self.device.status
        return status is not None and len(status) > 0

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        if self.is_ready():
            if self.sensor_device is None:
                return None
            return self.sensor_device.status.get(DPCode.VA_HUMIDITY)
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.is_ready():
            if self.sensor_device is None:
                return None
            return self.sensor_device.status.get(DPCode.VA_TEMPERATURE) / 10
        return None

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if self.is_ready():
            commands: list[dict[str, Any]] = []
            if hvac_mode == HVACMode.OFF:
                commands.append({"code": DPCode.POWER_OFF, "value": DPCode.POWER_OFF})
            elif hvac_mode == HVACMode.COOL:
                commands.append({"code": DPCode.POWER_ON, "value": DPCode.POWER_ON})
                commands.append({"code": DPCode.MODE, "value": "0"})
            elif hvac_mode == HVACMode.HEAT:
                commands = [{"code": DPCode.POWER_ON, "value": DPCode.POWER_ON}]
                commands.append({"code": DPCode.MODE, "value": "1"})
            elif hvac_mode == HVACMode.AUTO:
                commands = [{"code": DPCode.POWER_ON, "value": DPCode.POWER_ON}]
                commands.append({"code": DPCode.MODE, "value": "2"})
            self._send_command(commands)

    def turn_on(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        if self.is_ready():
            self._send_command([{"code": DPCode.POWER_ON, "value": DPCode.POWER_ON}])
            return
        return

    def turn_off(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        if self.is_ready():
            self._send_command([{"code": DPCode.POWER_OFF, "value": DPCode.POWER_OFF}])

    @staticmethod
    def read_status(api, device_id) -> dict:
        """Read device status using Tuya endpoint."""
        response = api.get(f"/v1.0/devices/{device_id}/status")
        status: dict[str, Any] = {}
        for item_status in response["result"]:
            if "code" in item_status and "value" in item_status:
                code = item_status["code"]
                value = item_status["value"]
                status.setdefault(code, value)
        return status

    @staticmethod
    async def async_fixup_device_status(
        hass: HomeAssistant, hass_data: HomeAssistantTuyaData, device_ids: list[str]
    ) -> None:
        """Fixup Device Status for Tuya infrared ac climate."""
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if device and device.category == CATEGORY_INFRARED_AC:
                api = hass_data.device_manager.api
                device.status = await hass.async_add_executor_job(
                    ft.partial(
                        TuyaInfraredClimateEntity.read_status,
                        api,
                        device_id,
                    )
                )

    async def async_update(self) -> None:
        """Retrieve latest state."""
        status = await self.hass.async_add_executor_job(
            ft.partial(
                TuyaInfraredClimateEntity.read_status,
                self.device_manager.api,
                self.device.id,
            )
        )
        self.device.status = status
