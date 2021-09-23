"""Support for Tuya Climate."""

from homeassistant.helpers.entity import Entity
import json
import logging

from homeassistant.components.climate import DOMAIN as DEVICE_DOMAIN
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from tuya_iot import TuyaDevice, TuyaDeviceManager

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

# Temerature unit
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

TUYA_HVAC_TO_HA = {
    "hot": HVAC_MODE_HEAT,
    "cold": HVAC_MODE_COOL,
    "wet": HVAC_MODE_DRY,
    "wind": HVAC_MODE_FAN_ONLY,
    "auto": HVAC_MODE_AUTO,
}

TUYA_ACTION_TO_HA = {
    "off": CURRENT_HVAC_OFF,
    "heating": CURRENT_HVAC_HEAT,
    "cooling": CURRENT_HVAC_COOL,
    "wind": CURRENT_HVAC_FAN,
    "auto": CURRENT_HVAC_IDLE,
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

    async def async_discover_device(dev_ids):
        """Discover and add a discovered tuya climate."""
        _LOGGER.debug(f"climate add->{dev_ids}")
        if not dev_ids:
            return
        entities = await hass.async_add_executor_job(_setup_entities, hass, entry, dev_ids)
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
    await async_discover_device(device_ids)


def _setup_entities(hass: HomeAssistant, entry:ConfigEntry, device_ids: list[str]) -> list[Entity]:
    """Set up Tuya Climate."""
    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    entities = []
    for device_id in device_ids:
        device = device_manager.device_map[device_id]
        if device is None:
            continue
        entities.append(TuyaHaClimate(device, device_manager))
        hass.data[DOMAIN][entry.entry_id][TUYA_HA_DEVICES].add(device_id)
    return entities


class TuyaHaClimate(TuyaHaEntity, ClimateEntity):
    """Tuya Switch Device."""

    def __init__(self, device: TuyaDevice, device_manager: TuyaDeviceManager):
        """Init Tuya Ha Climate."""
        super().__init__(device, device_manager)
        if DPCODE_C_F in self.tuya_device.status:
            self.dp_temp_unit = DPCODE_C_F
        else:
            self.dp_temp_unit = DPCODE_TEMP_UNIT_CONVERT

    def get_temp_set_scale(self) -> int:
        """Get temperature set scale."""
        __dp_temp_set = DPCODE_TEMP_SET if self.__is_celsius() else DPCODE_TEMP_SET_F
        __temp_set_value_range = json.loads(
            self.tuya_device.status_range.get(__dp_temp_set).values
        )
        return __temp_set_value_range.get("scale")

    def get_temp_current_scale(self) -> int:
        """Get temperature current scale."""
        __dp_temp_current = (
            DPCODE_TEMP_CURRENT if self.__is_celsius() else DPCODE_TEMP_CURRENT_F
        )
        __temp_current_value_range = json.loads(
            self.tuya_device.status_range.get(__dp_temp_current).values
        )
        return __temp_current_value_range.get("scale")

    # Functions

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

        self._send_command(commands)

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        self._send_command([{"code": DPCODE_FAN_SPEED_ENUM, "value": fan_mode}])

    def set_humidity(self, humidity):
        """Set new target humidity."""
        self._send_command([{"code": DPCODE_HUMIDITY_SET, "value": int(humidity)}])

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

        self._send_command(commands)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        _LOGGER.debug(f"climate temp->{kwargs}")
        code = DPCODE_TEMP_SET if self.__is_celsius() else DPCODE_TEMP_SET_F
        self._send_command(
            [
                {
                    "code": code,
                    "value": int(
                        kwargs["temperature"] * (10 ** self.get_temp_set_scale())
                    ),
                }
            ]
        )

    def __is_celsius(self) -> bool:
        if (
            self.dp_temp_unit in self.tuya_device.status
            and self.tuya_device.status.get(self.dp_temp_unit).lower() == "c"
        ):
            return True
        elif (
            DPCODE_TEMP_SET in self.tuya_device.status
            or DPCODE_TEMP_CURRENT in self.tuya_device.status
        ):
            return True
        return False

    @property
    def temperature_unit(self) -> str:
        """Return true if fan is on."""
        if self.__is_celsius():
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        if (
            DPCODE_TEMP_CURRENT not in self.tuya_device.status
            and DPCODE_TEMP_CURRENT_F not in self.tuya_device.status
        ):
            return None

        if self.__is_celsius():
            return (
                self.tuya_device.status.get(DPCODE_TEMP_CURRENT, 0)
                * 1.0
                / (10 ** self.get_temp_current_scale())
            )
        return (
            self.tuya_device.status.get(DPCODE_TEMP_CURRENT_F, 0)
            * 1.0
            / (10 ** self.get_temp_current_scale())
        )

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return int(self.tuya_device.status.get(DPCODE_HUMIDITY_CURRENT, 0))

    @property
    def target_temperature(self) -> float:
        """Return the temperature currently set to be reached."""
        return (
            self.tuya_device.status.get(DPCODE_TEMP_SET, 0)
            * 1.0
            / (10 ** self.get_temp_set_scale())
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.target_temperature_high

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.target_temperature_low

    @property
    def target_temperature_high(self) -> float:
        """Return the upper bound target temperature."""
        if self.__is_celsius():
            if DPCODE_TEMP_SET not in self.tuya_device.function:
                return 0
            temp_value = json.loads(
                self.tuya_device.function.get(DPCODE_TEMP_SET, {}).values
            )
            return temp_value.get("max", 0) * 1.0 / (10 ** self.get_temp_set_scale())
        if DPCODE_TEMP_SET_F not in self.tuya_device.function:
            return 0
        temp_value = json.loads(
            self.tuya_device.function.get(DPCODE_TEMP_SET_F, {}).values
        )
        return temp_value.get("max", 0) * 1.0 / (10 ** self.get_temp_set_scale())

    @property
    def target_temperature_low(self) -> float:
        """Return the lower bound target temperature."""
        if self.__is_celsius():
            if DPCODE_TEMP_SET not in self.tuya_device.function:
                return 0
            temp_value = json.loads(
                self.tuya_device.function.get(DPCODE_TEMP_SET, {}).values
            )
            low_value = (
                temp_value.get("min", 0) * 1.0 / (10 ** self.get_temp_set_scale())
            )
            return low_value
        if DPCODE_TEMP_SET_F not in self.tuya_device.function:
            return 0
        temp_value = json.loads(
            self.tuya_device.function.get(DPCODE_TEMP_SET_F, {}).values
        )
        return temp_value.get("min", 0) * 1.0 / (10 ** self.get_temp_set_scale())

    @property
    def target_temperature_step(self) -> float:
        """Return target temperature setp."""
        if (
            DPCODE_TEMP_SET not in self.tuya_device.status_range
            and DPCODE_TEMP_SET_F not in self.tuya_device.status_range
        ):
            return 1.0
        __temp_set_value_range = json.loads(
            self.tuya_device.status_range.get(
                DPCODE_TEMP_SET if self.__is_celsius() else DPCODE_TEMP_SET_F
            ).values
        )
        return (
            __temp_set_value_range.get("step", 0)
            * 1.0
            / (10 ** self.get_temp_set_scale())
        )

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
        return TUYA_HVAC_TO_HA[self.tuya_device.status.get(DPCODE_MODE)]

    @property
    def hvac_modes(self) -> list:
        """Return hvac modes for select."""
        if DPCODE_MODE not in self.tuya_device.function:
            return []
        modes = json.loads(self.tuya_device.function.get(DPCODE_MODE, {}).values).get(
            "range"
        )

        _LOGGER.debug(f"hvac_modes->{modes}")
        hvac_modes = [HVAC_MODE_OFF]
        for tuya_mode, ha_mode in TUYA_HVAC_TO_HA.items():
            if tuya_mode in modes:
                hvac_modes.append(ha_mode)

        return hvac_modes

    @property
    def preset_modes(self) -> list:
        """Return available presets."""
        if DPCODE_MODE not in self.tuya_device.function:
            return []
        modes = json.loads(self.tuya_device.function.get(DPCODE_MODE, {}).values).get(
            "range"
        )
        preset_modes = filter(lambda d: d not in TUYA_HVAC_TO_HA.keys(), modes)
        return list(preset_modes)

    @property
    def fan_mode(self) -> str:
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
    def swing_modes(self) -> list:
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
