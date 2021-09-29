"""Support for Tuya Climate."""

from __future__ import annotations

import json
import logging
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.climate import DOMAIN as DEVICE_DOMAIN, ClimateEntity
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
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import TuyaHaEntity
from .const import (
    DOMAIN,
    TUYA_DEVICE_MANAGER,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_DEVICES,
    TUYA_HA_TUYA_MAP,
)

_LOGGER = logging.getLogger(__name__)


# Air Conditioner
# https://developer.tuya.com/en/docs/iot/f?id=K9gf46qujdmwb
DPCODE_SWITCH = "switch"
DPCODE_TEMP_SET = "temp_set"
DPCODE_TEMP_SET_F = "temp_set_f"
DPCODE_MODE = "mode"
DPCODE_HUMIDITY_SET = "humidity_set"
DPCODE_FAN_SPEED_ENUM = "fan_speed_enum"

# Temperature unit
DPCODE_TEMP_UNIT_CONVERT = "temp_unit_convert"
DPCODE_C_F = "c_f"

# swing flap switch
DPCODE_SWITCH_HORIZONTAL = "switch_horizontal"
DPCODE_SWITCH_VERTICAL = "switch_vertical"

# status
DPCODE_TEMP_CURRENT = "temp_current"
DPCODE_TEMP_CURRENT_F = "temp_current_f"
DPCODE_HUMIDITY_CURRENT = "humidity_current"

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

TUYA_SUPPORT_TYPE = {
    "kt",  # Air conditioner
    "qn",  # Heater
    "wk",  # Thermostat
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya climate dynamically through tuya discovery."""
    _LOGGER.debug("climate init")

    hass.data[DOMAIN][entry.entry_id][TUYA_HA_TUYA_MAP][
        DEVICE_DOMAIN
    ] = TUYA_SUPPORT_TYPE

    @callback
    def async_discover_device(dev_ids: list[str]) -> None:
        """Discover and add a discovered tuya climate."""
        _LOGGER.debug("climate add-> %s", dev_ids)
        if not dev_ids:
            return
        entities = _setup_entities(hass, entry, dev_ids)
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, TUYA_DISCOVERY_NEW.format(DEVICE_DOMAIN), async_discover_device
        )
    )

    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    device_ids = []
    for (device_id, device) in device_manager.device_map.items():
        if device.category in TUYA_SUPPORT_TYPE:
            device_ids.append(device_id)
    async_discover_device(device_ids)


def _setup_entities(
    hass: HomeAssistant, entry: ConfigEntry, device_ids: list[str]
) -> list[Entity]:
    """Set up Tuya Climate."""
    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    entities: list[Entity] = []
    for device_id in device_ids:
        device = device_manager.device_map[device_id]
        if device is None:
            continue
        entities.append(TuyaHaClimate(device, device_manager))
        hass.data[DOMAIN][entry.entry_id][TUYA_HA_DEVICES].add(device_id)
    return entities


class TuyaHaClimate(TuyaHaEntity, ClimateEntity):
    """Tuya Switch Device."""

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager) -> None:
        """Init Tuya Ha Climate."""
        super().__init__(device, device_manager)
        if DPCODE_C_F in self.tuya_device.status:
            self.dp_temp_unit = DPCODE_C_F
        else:
            self.dp_temp_unit = DPCODE_TEMP_UNIT_CONVERT

    def get_temp_set_scale(self) -> int | None:
        """Get temperature set scale."""
        dp_temp_set = DPCODE_TEMP_SET if self.is_celsius() else DPCODE_TEMP_SET_F
        temp_set_value_range_item = self.tuya_device.status_range.get(dp_temp_set)
        if not temp_set_value_range_item:
            return None

        temp_set_value_range = json.loads(temp_set_value_range_item.values)
        return temp_set_value_range.get("scale")

    def get_temp_current_scale(self) -> int | None:
        """Get temperature current scale."""
        dp_temp_current = (
            DPCODE_TEMP_CURRENT if self.is_celsius() else DPCODE_TEMP_CURRENT_F
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
            commands.append({"code": DPCODE_SWITCH, "value": False})
        else:
            commands.append({"code": DPCODE_SWITCH, "value": True})

        for tuya_mode, ha_mode in TUYA_HVAC_TO_HA.items():
            if ha_mode == hvac_mode:
                commands.append({"code": DPCODE_MODE, "value": tuya_mode})
                break

        self._send_command(commands)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self._send_command([{"code": DPCODE_FAN_SPEED_ENUM, "value": fan_mode}])

    def set_humidity(self, humidity: float) -> None:
        """Set new target humidity."""
        self._send_command([{"code": DPCODE_HUMIDITY_SET, "value": int(humidity)}])

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        if swing_mode == SWING_BOTH:
            commands = [
                {"code": DPCODE_SWITCH_VERTICAL, "value": True},
                {"code": DPCODE_SWITCH_HORIZONTAL, "value": True},
            ]
        elif swing_mode == SWING_HORIZONTAL:
            commands = [
                {"code": DPCODE_SWITCH_VERTICAL, "value": False},
                {"code": DPCODE_SWITCH_HORIZONTAL, "value": True},
            ]
        elif swing_mode == SWING_VERTICAL:
            commands = [
                {"code": DPCODE_SWITCH_VERTICAL, "value": True},
                {"code": DPCODE_SWITCH_HORIZONTAL, "value": False},
            ]
        else:
            commands = [
                {"code": DPCODE_SWITCH_VERTICAL, "value": False},
                {"code": DPCODE_SWITCH_HORIZONTAL, "value": False},
            ]

        self._send_command(commands)

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        _LOGGER.debug("climate temp-> %s", kwargs)
        code = DPCODE_TEMP_SET if self.is_celsius() else DPCODE_TEMP_SET_F
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
            DPCODE_TEMP_SET in self.tuya_device.status
            or DPCODE_TEMP_CURRENT in self.tuya_device.status
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
            DPCODE_TEMP_CURRENT not in self.tuya_device.status
            and DPCODE_TEMP_CURRENT_F not in self.tuya_device.status
        ):
            return None

        temp_current_scale = self.get_temp_current_scale()
        if not temp_current_scale:
            return None

        if self.is_celsius():
            temperature = self.tuya_device.status.get(DPCODE_TEMP_CURRENT)
            if not temperature:
                return None
            return temperature * 1.0 / (10 ** temp_current_scale)

        temperature = self.tuya_device.status.get(DPCODE_TEMP_CURRENT_F)
        if not temperature:
            return None
        return temperature * 1.0 / (10 ** temp_current_scale)

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return int(self.tuya_device.status.get(DPCODE_HUMIDITY_CURRENT, 0))

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        temp_set_scale = self.get_temp_set_scale()
        if temp_set_scale is None:
            return None

        dpcode_temp_set = self.tuya_device.status.get(DPCODE_TEMP_SET)
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
            if DPCODE_TEMP_SET not in self.tuya_device.function:
                return DEFAULT_MAX_TEMP

            function_item = self.tuya_device.function.get(DPCODE_TEMP_SET)
            if function_item is None:
                return DEFAULT_MAX_TEMP

            temp_value = json.loads(function_item.values)

            temp_max = temp_value.get("max")
            if temp_max is None:
                return DEFAULT_MAX_TEMP
            return temp_max * 1.0 / (10 ** scale)
        if DPCODE_TEMP_SET_F not in self.tuya_device.function:
            return DEFAULT_MAX_TEMP

        function_item_f = self.tuya_device.function.get(DPCODE_TEMP_SET_F)
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
            if DPCODE_TEMP_SET not in self.tuya_device.function:
                return DEFAULT_MIN_TEMP

            function_temp_item = self.tuya_device.function.get(DPCODE_TEMP_SET)
            if function_temp_item is None:
                return DEFAULT_MIN_TEMP
            temp_value = json.loads(function_temp_item.values)
            temp_min = temp_value.get("min")
            if temp_min is None:
                return DEFAULT_MIN_TEMP
            return temp_min * 1.0 / (10 ** temp_set_scal)

        if DPCODE_TEMP_SET_F not in self.tuya_device.function:
            return DEFAULT_MIN_TEMP

        temp_value_temp_f = self.tuya_device.function.get(DPCODE_TEMP_SET_F)
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
            DPCODE_TEMP_SET not in self.tuya_device.status_range
            and DPCODE_TEMP_SET_F not in self.tuya_device.status_range
        ):
            return 1.0
        temp_set_value_range = json.loads(
            self.tuya_device.status_range.get(
                DPCODE_TEMP_SET if self.is_celsius() else DPCODE_TEMP_SET_F
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
        return int(self.tuya_device.status.get(DPCODE_HUMIDITY_SET, 0))

    @property
    def hvac_mode(self) -> str:
        """Return hvac mode."""
        if not self.tuya_device.status.get(DPCODE_SWITCH, False):
            return HVAC_MODE_OFF
        if DPCODE_MODE not in self.tuya_device.status:
            return HVAC_MODE_OFF
        if self.tuya_device.status.get(DPCODE_MODE) is not None:
            return TUYA_HVAC_TO_HA[self.tuya_device.status[DPCODE_MODE]]
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self) -> list[str]:
        """Return hvac modes for select."""
        if DPCODE_MODE not in self.tuya_device.function:
            return []
        modes = json.loads(self.tuya_device.function.get(DPCODE_MODE, {}).values).get(
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
        return self.tuya_device.status.get(DPCODE_FAN_SPEED_ENUM)

    @property
    def fan_modes(self) -> list[str]:
        """Return fan modes for select."""
        data = json.loads(
            self.tuya_device.function.get(DPCODE_FAN_SPEED_ENUM, {}).values
        ).get("range")
        return data

    @property
    def swing_mode(self) -> str:
        """Return swing mode."""
        mode = 0
        if (
            DPCODE_SWITCH_HORIZONTAL in self.tuya_device.status
            and self.tuya_device.status.get(DPCODE_SWITCH_HORIZONTAL)
        ):
            mode += 1
        if (
            DPCODE_SWITCH_VERTICAL in self.tuya_device.status
            and self.tuya_device.status.get(DPCODE_SWITCH_VERTICAL)
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
            DPCODE_TEMP_SET in self.tuya_device.status
            or DPCODE_TEMP_SET_F in self.tuya_device.status
        ):
            supports |= SUPPORT_TARGET_TEMPERATURE
        if DPCODE_FAN_SPEED_ENUM in self.tuya_device.status:
            supports |= SUPPORT_FAN_MODE
        if DPCODE_HUMIDITY_SET in self.tuya_device.status:
            supports |= SUPPORT_TARGET_HUMIDITY
        if (
            DPCODE_SWITCH_HORIZONTAL in self.tuya_device.status
            or DPCODE_SWITCH_VERTICAL in self.tuya_device.status
        ):
            supports |= SUPPORT_SWING_MODE
        return supports
