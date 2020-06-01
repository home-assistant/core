"""Support for Honeywell (US) Total Connect Comfort climate systems."""
import datetime
import logging
from typing import Any, Dict, List, Optional

import requests
import somecomfort
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_ON,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_FAN_ACTION = "fan_action"

CONF_COOL_AWAY_TEMPERATURE = "away_cool_temperature"
CONF_HEAT_AWAY_TEMPERATURE = "away_heat_temperature"

DEFAULT_COOL_AWAY_TEMPERATURE = 88
DEFAULT_HEAT_AWAY_TEMPERATURE = 61

HOLD_MODE_TEMPORARY = "temporary"
HOLD_MODE_PERMANENT = "permanent"
HOLD_MODE_SCHEDULE = "schedule"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(
            CONF_COOL_AWAY_TEMPERATURE, default=DEFAULT_COOL_AWAY_TEMPERATURE
        ): vol.Coerce(int),
        vol.Optional(
            CONF_HEAT_AWAY_TEMPERATURE, default=DEFAULT_HEAT_AWAY_TEMPERATURE
        ): vol.Coerce(int),
    }
)

HVAC_MODE_TO_HW_MODE = {
    "SwitchOffAllowed": {HVAC_MODE_OFF: "off"},
    "SwitchAutoAllowed": {HVAC_MODE_HEAT_COOL: "auto"},
    "SwitchCoolAllowed": {HVAC_MODE_COOL: "cool"},
    "SwitchHeatAllowed": {HVAC_MODE_HEAT: "heat"},
}
HW_MODE_TO_HVAC_MODE = {
    "off": HVAC_MODE_OFF,
    "emheat": HVAC_MODE_HEAT,
    "heat": HVAC_MODE_HEAT,
    "cool": HVAC_MODE_COOL,
    "auto": HVAC_MODE_HEAT_COOL,
}
HW_MODE_TO_HA_HVAC_ACTION = {
    "off": CURRENT_HVAC_IDLE,
    "fan": CURRENT_HVAC_FAN,
    "heat": CURRENT_HVAC_HEAT,
    "cool": CURRENT_HVAC_COOL,
}
FAN_MODE_TO_HW = {
    "fanModeOnAllowed": {FAN_ON: "on"},
    "fanModeAutoAllowed": {FAN_AUTO: "auto"},
    "fanModeCirculateAllowed": {FAN_DIFFUSE: "circulate"},
}
HW_FAN_MODE_TO_HA = {
    "on": FAN_ON,
    "auto": FAN_AUTO,
    "circulate": FAN_DIFFUSE,
    "follow schedule": FAN_AUTO,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Honeywell thermostat."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        client = somecomfort.SomeComfort(username, password)
    except somecomfort.AuthError:
        _LOGGER.error("Failed to login to honeywell account %s", username)
        return
    except somecomfort.SomeComfortError:
        _LOGGER.error(
            "Failed to initialize the Honeywell client: "
            "Check your configuration (username, password), "
            "or maybe you have exceeded the API rate limit?"
        )
        return

    dev_id = config.get("thermostat")
    loc_id = config.get("location")
    cool_away_temp = config.get(CONF_COOL_AWAY_TEMPERATURE)
    heat_away_temp = config.get(CONF_HEAT_AWAY_TEMPERATURE)

    add_entities(
        [
            HoneywellUSThermostat(
                client, device, cool_away_temp, heat_away_temp, username, password,
            )
            for location in client.locations_by_id.values()
            for device in location.devices_by_id.values()
            if (
                (not loc_id or location.locationid == loc_id)
                and (not dev_id or device.deviceid == dev_id)
            )
        ]
    )


class HoneywellUSThermostat(ClimateEntity):
    """Representation of a Honeywell US Thermostat."""

    def __init__(
        self, client, device, cool_away_temp, heat_away_temp, username, password,
    ):
        """Initialize the thermostat."""
        self._client = client
        self._device = device
        self._cool_away_temp = cool_away_temp
        self._heat_away_temp = heat_away_temp
        self._away = False
        self._away_timestamp = datetime.datetime.now()
        self._username = username
        self._password = password

        _LOGGER.debug("latestData = %s ", device._data)

        # not all honeywell HVACs support all modes
        mappings = [v for k, v in HVAC_MODE_TO_HW_MODE.items() if device.raw_ui_data[k]]
        self._hvac_mode_map = {k: v for d in mappings for k, v in d.items()}

        self._supported_features = SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE

        if HVAC_MODE_HEAT_COOL in mappings:
            self.supported_features |= SUPPORT_TARGET_TEMPERATURE_RANGE

        if device._data["canControlHumidification"]:
            self._supported_features |= SUPPORT_TARGET_HUMIDITY

        if device.raw_ui_data["SwitchEmergencyHeatAllowed"]:
            self._supported_features |= SUPPORT_AUX_HEAT

        if device._data["hasFan"]:
            # not all honeywell fans support all modes
            mappings = [v for k, v in FAN_MODE_TO_HW.items() if device.raw_fan_data[k]]
            self._fan_mode_map = {k: v for d in mappings for k, v in d.items()}

            self._supported_features |= SUPPORT_FAN_MODE

        if self._is_away_temp_set_for_mode():
            self._away = True

    @property
    def name(self) -> Optional[str]:
        """Return the name of the honeywell, if any."""
        return self._device.name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device specific state attributes."""
        honeywell = {}
        data = {
            "honeywell": honeywell,
            ATTR_FAN_ACTION: "running" if self._device.fan_running else "idle",
        }
        if self._device.raw_dr_data:
            honeywell["dr_phase"] = self._device.raw_dr_data.get("Phase")
        if HVAC_MODE_HEAT in self._hvac_mode_map:
            honeywell["hold_heat"] = self._hold_for_mode("heat")
        if HVAC_MODE_COOL in self._hvac_mode_map:
            honeywell["hold_cool"] = self._hold_for_mode("cool")
        data["hvac_mode"] = self.hvac_mode
        honeywell["system_mode"] = self._device.system_mode
        honeywell["equipment_output_status"] = self._device.equipment_output_status
        honeywell["device_id"] = self._device.deviceid
        honeywell["name"] = self._device.name
        honeywell["macid"] = self._device.mac_address
        return data

    def __repr__(self):
        """Print just its name."""
        return f"<Honeywell {self.name}: >"

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return self._supported_features

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self.hvac_mode in [HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL]:
            return self._device.raw_ui_data["CoolLowerSetptLimit"]
        if self.hvac_mode == HVAC_MODE_HEAT:
            return self._device.raw_ui_data["HeatLowerSetptLimit"]
        return None

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self.hvac_mode == HVAC_MODE_COOL:
            return self._device.raw_ui_data["CoolUpperSetptLimit"]
        if self.hvac_mode in [HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL]:
            return self._device.raw_ui_data["HeatUpperSetptLimit"]
        return None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS if self._device.temperature_unit == "C" else TEMP_FAHRENHEIT

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the current humidity."""
        return self._device.current_humidity

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return HW_MODE_TO_HVAC_MODE[self._device.system_mode]

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return list(self._hvac_mode_map)

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported."""
        if self.hvac_mode == HVAC_MODE_OFF:
            return None
        return HW_MODE_TO_HA_HVAC_ACTION[self._device.equipment_output_status]

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_COOL:
            return self._device.setpoint_cool
        if self.hvac_mode == HVAC_MODE_HEAT:
            return self._device.setpoint_heat
        return None

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the highbound target temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_HEAT_COOL:
            return self._device.setpoint_cool
        return None

    @property
    def hold_mode(self) -> Optional[bool]:
        """Return if the thermostat is in permanent hold."""
        return self._hold

    @property
    def _hold(self) -> Optional[bool]:
        mode = self._current_system_mode()
        if mode not in ["heat", "cool"]:
            return None
        return self._hold_for_mode(mode)

    def _hold_for_mode(self, mode: str) -> Optional[bool]:
        hold_mode = getattr(self._device, f"hold_{mode}")
        if hold_mode is True:
            return HOLD_MODE_PERMANENT
        if hold_mode is False:
            return HOLD_MODE_SCHEDULE
        return HOLD_MODE_TEMPORARY

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the lowbound target temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_HEAT_COOL:
            return self._device.setpoint_heat
        return None

    @property
    def away(self) -> bool:
        """Return whether or not the thermostat is away. Requires away boolean and validation of settings."""
        if self._away:
            if self._is_away_temp_set_for_mode():
                return True
            else:
                if (datetime.datetime.now() - self._away_timestamp).seconds > 60:
                    self._away = False
        return False

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        return PRESET_AWAY if self.away else PRESET_NONE

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return [PRESET_NONE, PRESET_AWAY]

    @property
    def is_aux_heat(self) -> Optional[str]:
        """Return true if aux heater."""
        return self._device.system_mode == "emheat"

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan setting."""
        return HW_FAN_MODE_TO_HA[self._device.fan_mode]

    @property
    def fan_modes(self) -> Optional[List[str]]:
        """Return the list of available fan modes."""
        return list(self._fan_mode_map)

    def _set_temperature(self, temperature: int, mode: str) -> None:
        """Set new target temperature."""
        try:
            # Set temperature
            setattr(self._device, f"setpoint_{mode}", temperature)
        except somecomfort.SomeComfortError:
            _LOGGER.error("Temperature %.1f out of range", temperature)

    def _set_temperature_range(self, temperature_low, temperature_high) -> None:
        temperature = None
        try:
            if temperature_high:
                temperature = temperature_high
                self._device.setpoint_cool = temperature_high
            if temperature_low:
                temperature = temperature_low
                self._device.setpoint_heat = temperature_low
        except somecomfort.SomeComfortError as err:
            _LOGGER.error("Invalid temperature %s: %s", temperature, err)

    def _set_temporary_hold(self, mode: str) -> None:
        # Set temporary hold if we aren't in permanent hold
        if getattr(self._device, f"hold_{mode}") is False:
            # Get next period key
            next_period_key = f"{mode.capitalize()}NextPeriod"
            # Get next period raw value
            next_period = self._device.raw_ui_data.get(next_period_key)
            # Get next period time
            hour, minute = divmod(next_period * 15, 60)
            # Set hold time
            setattr(self._device, f"hold_{mode}", datetime.time(hour, minute))

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if {HVAC_MODE_COOL, HVAC_MODE_HEAT} & set(self._hvac_mode_map):
            temperature = kwargs.get(ATTR_TEMPERATURE)
            if temperature is not None:
                mode = self._current_system_mode()
                self._set_temporary_hold(mode)
                self._set_temperature(temperature, mode)

        if HVAC_MODE_HEAT_COOL in self._hvac_mode_map:
            temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
            temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            self._set_temperature_range(temperature_low, temperature_high)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self._device.fan_mode = self._fan_mode_map[fan_mode]

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        new_mode = self._hvac_mode_map[hvac_mode]
        self._device.system_mode = new_mode

    def _away_target_for_mode(self, mode: str) -> int:
        """Check for away mode settings."""
        return int(getattr(self, f"_{mode}_away_temp"))

    def _is_away_temp_set_for_mode(self) -> bool:
        """Check if away mode is properly set."""
        if self.hold_mode != HOLD_MODE_PERMANENT:
            return False
        try:
            # Get current mode
            mode = self._device.system_mode
        except somecomfort.SomeComfortError:
            _LOGGER.error("Can not get system mode")
            return False
        # Get temperature
        hw_target = getattr(self._device, f"setpoint_{mode}")
        away_target = self._away_target_for_mode(mode)
        return hw_target == away_target

    def _turn_away_mode_on(self) -> None:
        """Turn away on.

        Somecomfort does have a proprietary away mode, but it doesn't really
        work the way it should. For example: If you set a temperature manually
        it doesn't get overwritten when away mode is switched on.
        """
        self._away = True
        self._away_timestamp = datetime.datetime.now()
        mode = self._current_system_mode()
        self._set_permanent_hold(mode)
        target_temp = self._away_target_for_mode(mode)
        self._set_temperature(target_temp, mode)

    def _set_permanent_hold(self, mode) -> None:
        # Set permanent hold
        setattr(self._device, f"hold_{mode}", True)

    def _current_system_mode(self) -> str:
        return self._device.system_mode

    def _disable_holds(self) -> None:
        try:
            # Disabling all hold modes
            self._device.hold_cool = False
            self._device.hold_heat = False
        except somecomfort.SomeComfortError:
            _LOGGER.error("Can not stop hold mode")

    def _turn_away_mode_off(self) -> None:
        """Turn away off."""
        self._away = False
        self._disable_holds()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_AWAY:
            self._turn_away_mode_on()
        else:
            self._turn_away_mode_off()

    def turn_aux_heat_on(self) -> None:
        """Turn auxiliary heater on."""
        self._device.system_mode = "emheat"

    def turn_aux_heat_off(self) -> None:
        """Turn auxiliary heater off."""
        if HVAC_MODE_HEAT in self.hvac_modes:
            self.set_hvac_mode(HVAC_MODE_HEAT)
        else:
            self.set_hvac_mode(HVAC_MODE_OFF)

    def _retry(self) -> bool:
        """Recreate a new somecomfort client.

        When we got an error, the best way to be sure that the next query
        will succeed, is to recreate a new somecomfort client.
        """
        try:
            self._client = somecomfort.SomeComfort(self._username, self._password)
        except somecomfort.AuthError:
            _LOGGER.error("Failed to login to honeywell account %s", self._username)
            return False
        except somecomfort.SomeComfortError as ex:
            _LOGGER.error("Failed to initialize honeywell client: %s", str(ex))
            return False

        devices = [
            device
            for location in self._client.locations_by_id.values()
            for device in location.devices_by_id.values()
            if device.name == self._device.name
        ]

        if len(devices) != 1:
            _LOGGER.error("Failed to find device %s", self._device.name)
            return False

        self._device = devices[0]
        return True

    def update(self) -> None:
        """Update the state."""
        retries = 3
        while retries > 0:
            try:
                self._device.refresh()
                break
            except (
                somecomfort.client.APIRateLimited,
                OSError,
                requests.exceptions.ReadTimeout,
            ) as exp:
                retries -= 1
                if retries == 0:
                    raise exp
                if not self._retry():
                    raise exp
                _LOGGER.error("SomeComfort update failed, Retrying - Error: %s", exp)

        _LOGGER.debug(
            "latestData = %s ", self._device._data  # pylint: disable=protected-access
        )
