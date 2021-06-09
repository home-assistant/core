#!/usr/bin/env python3
"""Support for Tuya Climate."""

import json
import logging
from typing import List

from homeassistant.components.climate import (
    DOMAIN as DEVICE_DOMAIN,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    ClimateEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .base import TuyaHaDevice
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
DPCODE_TEMP_UNIT_CONVERT = "temp_unit_convert"
DPCODE_FAN_SPEED_ENUM = "fan_speed_enum"

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

TUYA_HVAC_TO_HA = {
    "hot": "heat",
    "cold": "cool",
    "wet": "dry",
    "wind": "fan_only",
    "auto": "auto",
}

TUYA_SUPPORT_TYPE = {"kt", "qn"}  # Air conditioner  # Heater


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up tuya climate dynamically through tuya discovery."""
    print("climate init")

    hass.data[DOMAIN][TUYA_HA_TUYA_MAP].update({DEVICE_DOMAIN: TUYA_SUPPORT_TYPE})

    async def async_discover_device(dev_ids):
        """Discover and add a discovered tuya climate."""
        print("climate add->", dev_ids)
        if not dev_ids:
            return
        entities = await hass.async_add_executor_job(_setup_entities, hass, dev_ids)
        hass.data[DOMAIN][TUYA_HA_DEVICES].extend(entities)
        async_add_entities(entities)

    async_dispatcher_connect(
        hass, TUYA_DISCOVERY_NEW.format(DEVICE_DOMAIN), async_discover_device
    )

    device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
    device_ids = []
    for (device_id, device) in device_manager.deviceMap.items():
        if device.category in TUYA_SUPPORT_TYPE:
            device_ids.append(device_id)
    await async_discover_device(device_ids)


def _setup_entities(hass, device_ids: List):
    """Set up Tuya Climate."""
    device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
    entities = []
    for device_id in device_ids:
        device = device_manager.deviceMap[device_id]
        if device is None:
            continue
        entities.append(TuyaHaClimate(device, device_manager))
    return entities


class TuyaHaClimate(TuyaHaDevice, ClimateEntity):
    """Tuya Switch Device."""

    target_temp = 0.0
    target_h = 30

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        commands = []
        if hvac_mode == HVAC_MODE_OFF:
            commands.append({"code": DPCODE_SWITCH, "value": False})
        else:
            commands.append({"code": DPCODE_SWITCH, "value": True})

        for tuya_mode, ha_mode in TUYA_HVAC_TO_HA.items():
            if ha_mode == hvac_mode:
                commands.append({"code": DPCODE_MODE, "value": tuya_mode})

        self.tuya_device_manager.sendCommands(self.tuya_device.id, commands)

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        self.tuya_device_manager.sendCommands(
            self.tuya_device.id, [{"code": DPCODE_FAN_SPEED_ENUM, "value": fan_mode}]
        )

    def set_humidity(self, humidity):
        """Set new target humidity."""
        response = self.tuya_device_manager.sendCommands(
            self.tuya_device.id, [{"code": DPCODE_HUMIDITY_SET, "value": int(humidity)}]
        )
        if response.get("success", False):
            self.target_h = humidity

    def set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        commands = []
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

        self.tuya_device_manager.sendCommands(self.tuya_device.id, commands)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        print("climate temp->", kwargs)
        code = (
            DPCODE_TEMP_SET
            if self.tuya_device.status.get(DPCODE_TEMP_UNIT_CONVERT) == "c"
            else DPCODE_TEMP_SET_F
        )
        response = self.tuya_device_manager.sendCommands(
            self.tuya_device.id, [{"code": code, "value": int(kwargs["temperature"])}]
        )
        if response.get("success", False):
            self.target_temp = kwargs["temperature"]

    # property

    @property
    def temperature_unit(self) -> str:
        """Return true if fan is on."""
        if self.tuya_device.status.get(DPCODE_TEMP_UNIT_CONVERT) == "c":
            return TEMP_CELSIUS
        else:
            return TEMP_FAHRENHEIT

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        if self.tuya_device.status.get(DPCODE_TEMP_UNIT_CONVERT) == "c":
            return self.tuya_device.status.get(DPCODE_TEMP_CURRENT, 0)
        else:
            return self.tuya_device.status.get(DPCODE_TEMP_CURRENT_F, 0)

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return int(self.tuya_device.status.get(DPCODE_HUMIDITY_CURRENT, 0))

    @property
    def target_temperature(self) -> float:
        """Return the temperature currently set to be reached."""
        return self.target_temp

    @property
    def target_temperature_high(self) -> float:
        """Return the upper bound target temperature."""
        if self.tuya_device.status.get(DPCODE_TEMP_UNIT_CONVERT) == "c":
            temp_value = json.loads(
                self.tuya_device.function.get(DPCODE_TEMP_SET, {}).values
            )
            return temp_value.get("max", 0)
        else:
            temp_value = json.loads(
                self.tuya_device.function.get(DPCODE_TEMP_SET_F, {}).values
            )
            return temp_value.get("max", 0)

    @property
    def target_temperature_low(self) -> float:
        """Return the lower bound target temperature."""
        if self.tuya_device.status.get(DPCODE_TEMP_UNIT_CONVERT) == "c":
            temp_value = json.loads(
                self.tuya_device.function.get(DPCODE_TEMP_SET, {}).values
            )
            return temp_value.get("min", 0)
        else:
            temp_value = json.loads(
                self.tuya_device.function.get(DPCODE_TEMP_SET_F, {}).values
            )
            return temp_value.get("min", 0)

    @property
    def target_temperature_step(self) -> float:
        """Return target temperature setp."""
        return 1

    @property
    def target_humidity(self) -> int:
        """Return target humidity."""
        return int(self.target_h)

    @property
    def hvac_mode(self) -> str:
        """Return hvac mode."""
        if not self.tuya_device.status.get(DPCODE_SWITCH):
            return HVAC_MODE_OFF

        return TUYA_HVAC_TO_HA[self.tuya_device.status.get(DPCODE_MODE)]

    @property
    def hvac_modes(self) -> List:
        """Return hvac modes for select."""
        modes = json.loads(self.tuya_device.function.get(DPCODE_MODE, {}).values).get(
            "range"
        )

        print("hvac_modes->", modes)
        hvac_modes = [HVAC_MODE_OFF]
        for tuya_mode, ha_mode in TUYA_HVAC_TO_HA.items():
            if tuya_mode in modes:
                hvac_modes.append(ha_mode)

        return hvac_modes

    @property
    def fan_mode(self) -> str:
        """Return fan mode."""
        return self.tuya_device.status.get(DPCODE_FAN_SPEED_ENUM)

    @property
    def fan_modes(self) -> List[str]:
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
        elif mode == 2:
            return SWING_VERTICAL
        elif mode == 1:
            return SWING_HORIZONTAL
        else:
            return SWING_OFF

    @property
    def swing_modes(self) -> List:
        """Return swing mode for select."""
        return [SWING_OFF, SWING_HORIZONTAL, SWING_VERTICAL, SWING_BOTH]

    @property
    def supported_features(self):
        """Flag supported features."""
        supports = 0
        if (
            DPCODE_TEMP_SET in self.tuya_device.status
            or DPCODE_TEMP_SET_F in self.tuya_device.status
        ):
            supports = supports | SUPPORT_TARGET_TEMPERATURE
        if DPCODE_FAN_SPEED_ENUM in self.tuya_device.status:
            supports = supports | SUPPORT_FAN_MODE
        if DPCODE_HUMIDITY_SET in self.tuya_device.status:
            supports = supports | SUPPORT_TARGET_HUMIDITY
        if (
            DPCODE_SWITCH_HORIZONTAL in self.tuya_device.status
            or DPCODE_SWITCH_VERTICAL in self.tuya_device.status
        ):
            supports = supports | SUPPORT_SWING_MODE
        return supports
