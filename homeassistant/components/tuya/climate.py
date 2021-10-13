"""Support for Tuya Climate."""

from __future__ import annotations

import json
import logging
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaHaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode

_LOGGER = logging.getLogger(__name__)

SWING_OFF = "swing_off"
SWING_VERTICAL = "swing_vertical"
SWING_HORIZONTAL = "swing_horizontal"
SWING_BOTH = "swing_both"

DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35

TUYA_HVAC_TO_HA = {
    "hot": HVAC_MODE_HEAT,
    "cold": HVAC_MODE_COOL,
    "wet": HVAC_MODE_DRY,
    "wind": HVAC_MODE_FAN_ONLY,
    "auto": HVAC_MODE_AUTO,
}

# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
TUYA_SUPPORT_TYPE = {
    "kt",  # Air conditioner
    "qn",  # Heater
    "wk",  # Thermostat
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya climate dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya climate."""
        entities: list[TuyaHaClimate] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if device and device.category in TUYA_SUPPORT_TYPE:
                entities.append(TuyaHaClimate(device, hass_data.device_manager))
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaHaClimate(TuyaHaEntity, ClimateEntity):
    """Tuya Switch Device."""

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init Tuya Ha Climate."""
        super().__init__(device, device_manager)
        if DPCode.C_F in self.tuya_device.status:
            self.dp_temp_unit = DPCode.C_F
        else:
            self.dp_temp_unit = DPCode.TEMP_UNIT_CONVERT

    def get_temp_set_scale(self) -> int | None:
        """Get temperature set scale."""
        dp_temp_set = DPCode.TEMP_SET if self.is_celsius() else DPCode.TEMP_SET_F
        temp_set_value_range_item = self.tuya_device.status_range.get(dp_temp_set)
        if not temp_set_value_range_item:
            return None

        temp_set_value_range = json.loads(temp_set_value_range_item.values)
        return temp_set_value_range.get("scale")

    def get_temp_current_scale(self) -> int | None:
        """Get temperature current scale."""
        dp_temp_current = (
            DPCode.TEMP_CURRENT if self.is_celsius() else DPCode.TEMP_CURRENT_F
        )
        temp_current_value_range_item = self.tuya_device.status_range.get(
            dp_temp_current
        )
        if not temp_current_value_range_item:
            return None

        temp_current_value_range = json.loads(temp_current_value_range_item.values)
        return temp_current_value_range.get("scale")

    # Functions

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        commands = []
        if hvac_mode == HVAC_MODE_OFF:
            commands.append({"code": DPCode.SWITCH, "value": False})
        else:
            commands.append({"code": DPCode.SWITCH, "value": True})

        for tuya_mode, ha_mode in TUYA_HVAC_TO_HA.items():
            if ha_mode == hvac_mode:
                commands.append({"code": DPCode.MODE, "value": tuya_mode})
                break

        self._send_command(commands)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self._send_command([{"code": DPCode.FAN_SPEED_ENUM, "value": fan_mode}])

    def set_humidity(self, humidity: float) -> None:
        """Set new target humidity."""
        self._send_command([{"code": DPCode.HUMIDITY_SET, "value": int(humidity)}])

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        if swing_mode == SWING_BOTH:
            commands = [
                {"code": DPCode.SWITCH_VERTICAL, "value": True},
                {"code": DPCode.SWITCH_HORIZONTAL, "value": True},
            ]
        elif swing_mode == SWING_HORIZONTAL:
            commands = [
                {"code": DPCode.SWITCH_VERTICAL, "value": False},
                {"code": DPCode.SWITCH_HORIZONTAL, "value": True},
            ]
        elif swing_mode == SWING_VERTICAL:
            commands = [
                {"code": DPCode.SWITCH_VERTICAL, "value": True},
                {"code": DPCode.SWITCH_HORIZONTAL, "value": False},
            ]
        else:
            commands = [
                {"code": DPCode.SWITCH_VERTICAL, "value": False},
                {"code": DPCode.SWITCH_HORIZONTAL, "value": False},
            ]

        self._send_command(commands)

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        _LOGGER.debug("climate temp-> %s", kwargs)
        code = DPCode.TEMP_SET if self.is_celsius() else DPCode.TEMP_SET_F
        temp_set_scale = self.get_temp_set_scale()
        if not temp_set_scale:
            return

        self._send_command(
            [
                {
                    "code": code,
                    "value": int(kwargs["temperature"] * (10 ** temp_set_scale)),
                }
            ]
        )

    def is_celsius(self) -> bool:
        """Return True if device reports in Celsius."""
        if (
            self.dp_temp_unit in self.tuya_device.status
            and self.tuya_device.status.get(self.dp_temp_unit).lower() == "c"
        ):
            return True
        if (
            DPCode.TEMP_SET in self.tuya_device.status
            or DPCode.TEMP_CURRENT in self.tuya_device.status
        ):
            return True
        return False

    @property
    def temperature_unit(self) -> str:
        """Return true if fan is on."""
        if self.is_celsius():
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if (
            DPCode.TEMP_CURRENT not in self.tuya_device.status
            and DPCode.TEMP_CURRENT_F not in self.tuya_device.status
        ):
            return None

        temp_current_scale = self.get_temp_current_scale()
        if not temp_current_scale:
            return None

        if self.is_celsius():
            temperature = self.tuya_device.status.get(DPCode.TEMP_CURRENT)
            if not temperature:
                return None
            return temperature * 1.0 / (10 ** temp_current_scale)

        temperature = self.tuya_device.status.get(DPCode.TEMP_CURRENT_F)
        if not temperature:
            return None
        return temperature * 1.0 / (10 ** temp_current_scale)

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return int(self.tuya_device.status.get(DPCode.HUMIDITY_CURRENT, 0))

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        temp_set_scale = self.get_temp_set_scale()
        if temp_set_scale is None:
            return None

        dpcode_temp_set = self.tuya_device.status.get(DPCode.TEMP_SET)
        if dpcode_temp_set is None:
            return None

        return dpcode_temp_set * 1.0 / (10 ** temp_set_scale)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        scale = self.get_temp_set_scale()
        if scale is None:
            return DEFAULT_MAX_TEMP

        if self.is_celsius():
            if DPCode.TEMP_SET not in self.tuya_device.function:
                return DEFAULT_MAX_TEMP

            function_item = self.tuya_device.function.get(DPCode.TEMP_SET)
            if function_item is None:
                return DEFAULT_MAX_TEMP

            temp_value = json.loads(function_item.values)

            temp_max = temp_value.get("max")
            if temp_max is None:
                return DEFAULT_MAX_TEMP
            return temp_max * 1.0 / (10 ** scale)
        if DPCode.TEMP_SET_F not in self.tuya_device.function:
            return DEFAULT_MAX_TEMP

        function_item_f = self.tuya_device.function.get(DPCode.TEMP_SET_F)
        if function_item_f is None:
            return DEFAULT_MAX_TEMP

        temp_value_f = json.loads(function_item_f.values)

        temp_max_f = temp_value_f.get("max")
        if temp_max_f is None:
            return DEFAULT_MAX_TEMP
        return temp_max_f * 1.0 / (10 ** scale)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        temp_set_scal = self.get_temp_set_scale()
        if temp_set_scal is None:
            return DEFAULT_MIN_TEMP

        if self.is_celsius():
            if DPCode.TEMP_SET not in self.tuya_device.function:
                return DEFAULT_MIN_TEMP

            function_temp_item = self.tuya_device.function.get(DPCode.TEMP_SET)
            if function_temp_item is None:
                return DEFAULT_MIN_TEMP
            temp_value = json.loads(function_temp_item.values)
            temp_min = temp_value.get("min")
            if temp_min is None:
                return DEFAULT_MIN_TEMP
            return temp_min * 1.0 / (10 ** temp_set_scal)

        if DPCode.TEMP_SET_F not in self.tuya_device.function:
            return DEFAULT_MIN_TEMP

        temp_value_temp_f = self.tuya_device.function.get(DPCode.TEMP_SET_F)
        if temp_value_temp_f is None:
            return DEFAULT_MIN_TEMP
        temp_value_f = json.loads(temp_value_temp_f.values)

        temp_min_f = temp_value_f.get("min")
        if temp_min_f is None:
            return DEFAULT_MIN_TEMP

        return temp_min_f * 1.0 / (10 ** temp_set_scal)

    @property
    def target_temperature_step(self) -> float | None:
        """Return target temperature setp."""
        if (
            DPCode.TEMP_SET not in self.tuya_device.status_range
            and DPCode.TEMP_SET_F not in self.tuya_device.status_range
        ):
            return 1.0
        temp_set_value_range = json.loads(
            self.tuya_device.status_range.get(
                DPCode.TEMP_SET if self.is_celsius() else DPCode.TEMP_SET_F
            ).values
        )
        step = temp_set_value_range.get("step")
        if step is None:
            return None

        temp_set_scale = self.get_temp_set_scale()
        if temp_set_scale is None:
            return None

        return step * 1.0 / (10 ** temp_set_scale)

    @property
    def target_humidity(self) -> int:
        """Return target humidity."""
        return int(self.tuya_device.status.get(DPCode.HUMIDITY_SET, 0))

    @property
    def hvac_mode(self) -> str:
        """Return hvac mode."""
        if not self.tuya_device.status.get(DPCode.SWITCH, False):
            return HVAC_MODE_OFF
        if DPCode.MODE not in self.tuya_device.status:
            return HVAC_MODE_OFF
        if self.tuya_device.status.get(DPCode.MODE) is not None:
            return TUYA_HVAC_TO_HA[self.tuya_device.status[DPCode.MODE]]
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self) -> list[str]:
        """Return hvac modes for select."""
        if DPCode.MODE not in self.tuya_device.function:
            return []
        modes = json.loads(self.tuya_device.function.get(DPCode.MODE, {}).values).get(
            "range"
        )

        hvac_modes = [HVAC_MODE_OFF]
        for tuya_mode, ha_mode in TUYA_HVAC_TO_HA.items():
            if tuya_mode in modes:
                hvac_modes.append(ha_mode)

        return hvac_modes

    @property
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        return self.tuya_device.status.get(DPCode.FAN_SPEED_ENUM)

    @property
    def fan_modes(self) -> list[str]:
        """Return fan modes for select."""
        fan_speed_device_function = self.tuya_device.function.get(DPCode.FAN_SPEED_ENUM)
        if not fan_speed_device_function:
            return []
        return json.loads(fan_speed_device_function.values).get("range", [])

    @property
    def swing_mode(self) -> str:
        """Return swing mode."""
        mode = 0
        if (
            DPCode.SWITCH_HORIZONTAL in self.tuya_device.status
            and self.tuya_device.status.get(DPCode.SWITCH_HORIZONTAL)
        ):
            mode += 1
        if (
            DPCode.SWITCH_VERTICAL in self.tuya_device.status
            and self.tuya_device.status.get(DPCode.SWITCH_VERTICAL)
        ):
            mode += 2

        if mode == 3:
            return SWING_BOTH
        if mode == 2:
            return SWING_VERTICAL
        if mode == 1:
            return SWING_HORIZONTAL
        return SWING_OFF

    @property
    def swing_modes(self) -> list[str]:
        """Return swing mode for select."""
        return [SWING_OFF, SWING_HORIZONTAL, SWING_VERTICAL, SWING_BOTH]

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supports = 0
        if (
            DPCode.TEMP_SET in self.tuya_device.status
            or DPCode.TEMP_SET_F in self.tuya_device.status
        ):
            supports |= SUPPORT_TARGET_TEMPERATURE
        if DPCode.FAN_SPEED_ENUM in self.tuya_device.status:
            supports |= SUPPORT_FAN_MODE
        if DPCode.HUMIDITY_SET in self.tuya_device.status:
            supports |= SUPPORT_TARGET_HUMIDITY
        if (
            DPCode.SWITCH_HORIZONTAL in self.tuya_device.status
            or DPCode.SWITCH_VERTICAL in self.tuya_device.status
        ):
            supports |= SUPPORT_SWING_MODE
        return supports
