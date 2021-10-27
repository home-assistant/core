"""Support for Fibaro thermostats."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from . import FIBARO_DEVICES, FibaroDevice

PRESET_RESUME = "resume"
PRESET_MOIST = "moist"
PRESET_FURNACE = "furnace"
PRESET_CHANGEOVER = "changeover"
PRESET_ECO_HEAT = "eco_heat"
PRESET_ECO_COOL = "eco_cool"
PRESET_FORCE_OPEN = "force_open"

_LOGGER = logging.getLogger(__name__)

# SDS13781-10 Z-Wave Application Command Class Specification 2019-01-04
# Table 128, Thermostat Fan Mode Set version 4::Fan Mode encoding
FANMODES = {
    0: "off",
    1: "low",
    2: "auto_high",
    3: "medium",
    4: "auto_medium",
    5: "high",
    6: "circulation",
    7: "humidity_circulation",
    8: "left_right",
    9: "up_down",
    10: "quiet",
    128: "auto",
}

HA_FANMODES = {v: k for k, v in FANMODES.items()}

# SDS13781-10 Z-Wave Application Command Class Specification 2019-01-04
# Table 130, Thermostat Mode Set version 3::Mode encoding.
# 4 AUXILIARY
OPMODES_PRESET = {
    5: PRESET_RESUME,
    7: PRESET_FURNACE,
    9: PRESET_MOIST,
    10: PRESET_CHANGEOVER,
    11: PRESET_ECO_HEAT,
    12: PRESET_ECO_COOL,
    13: PRESET_AWAY,
    15: PRESET_BOOST,
    31: PRESET_FORCE_OPEN,
}

HA_OPMODES_PRESET = {v: k for k, v in OPMODES_PRESET.items()}

OPMODES_HVAC = {
    0: HVAC_MODE_OFF,
    1: HVAC_MODE_HEAT,
    2: HVAC_MODE_COOL,
    3: HVAC_MODE_AUTO,
    4: HVAC_MODE_HEAT,
    5: HVAC_MODE_AUTO,
    6: HVAC_MODE_FAN_ONLY,
    7: HVAC_MODE_HEAT,
    8: HVAC_MODE_DRY,
    9: HVAC_MODE_DRY,
    10: HVAC_MODE_AUTO,
    11: HVAC_MODE_HEAT,
    12: HVAC_MODE_COOL,
    13: HVAC_MODE_AUTO,
    15: HVAC_MODE_AUTO,
    31: HVAC_MODE_HEAT,
}

HA_OPMODES_HVAC = {
    HVAC_MODE_OFF: 0,
    HVAC_MODE_HEAT: 1,
    HVAC_MODE_COOL: 2,
    HVAC_MODE_AUTO: 3,
    HVAC_MODE_FAN_ONLY: 6,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Fibaro controller devices."""
    if discovery_info is None:
        return

    add_entities(
        [FibaroThermostat(device) for device in hass.data[FIBARO_DEVICES]["climate"]],
        True,
    )


class FibaroThermostat(FibaroDevice, ClimateEntity):
    """Representation of a Fibaro Thermostat."""

    def __init__(self, fibaro_device):
        """Initialize the Fibaro device."""
        super().__init__(fibaro_device)
        self._temp_sensor_device = None
        self._target_temp_device = None
        self._op_mode_device = None
        self._fan_mode_device = None
        self._support_flags = 0
        self.entity_id = f"climate.{self.ha_id}"
        self._hvac_support = []
        self._preset_support = []
        self._fan_support = []

        siblings = fibaro_device.fibaro_controller.get_siblings(fibaro_device)
        _LOGGER.debug("%s siblings: %s", fibaro_device.ha_id, siblings)
        tempunit = "C"
        for device in siblings:
            # Detecting temperature device, one strong and one weak way of
            # doing so, so we prefer the hard evidence, if there is such.
            if device.type == "com.fibaro.temperatureSensor":
                self._temp_sensor_device = FibaroDevice(device)
                tempunit = device.properties.unit
            elif (
                self._temp_sensor_device is None
                and "unit" in device.properties
                and (
                    "value" in device.properties
                    or "heatingThermostatSetpoint" in device.properties
                )
                and device.properties.unit in ("C", "F")
            ):
                self._temp_sensor_device = FibaroDevice(device)
                tempunit = device.properties.unit

            if (
                "setTargetLevel" in device.actions
                or "setThermostatSetpoint" in device.actions
                or "setHeatingThermostatSetpoint" in device.actions
            ):
                self._target_temp_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_TARGET_TEMPERATURE
                tempunit = device.properties.unit

            if "setMode" in device.actions or "setOperatingMode" in device.actions:
                self._op_mode_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_PRESET_MODE

            if "setFanMode" in device.actions:
                self._fan_mode_device = FibaroDevice(device)
                self._support_flags |= SUPPORT_FAN_MODE

        if tempunit == "F":
            self._unit_of_temp = TEMP_FAHRENHEIT
        else:
            self._unit_of_temp = TEMP_CELSIUS

        if self._fan_mode_device:
            fan_modes = (
                self._fan_mode_device.fibaro_device.properties.supportedModes.split(",")
            )
            for mode in fan_modes:
                mode = int(mode)
                if mode not in FANMODES:
                    _LOGGER.warning("%d unknown fan mode", mode)
                    continue
                self._fan_support.append(FANMODES[int(mode)])

        if self._op_mode_device:
            prop = self._op_mode_device.fibaro_device.properties
            if "supportedOperatingModes" in prop:
                op_modes = prop.supportedOperatingModes.split(",")
            elif "supportedModes" in prop:
                op_modes = prop.supportedModes.split(",")
            for mode in op_modes:
                mode = int(mode)
                if mode in OPMODES_HVAC:
                    mode_ha = OPMODES_HVAC[mode]
                    if mode_ha not in self._hvac_support:
                        self._hvac_support.append(mode_ha)
                if mode in OPMODES_PRESET:
                    self._preset_support.append(OPMODES_PRESET[mode])

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        _LOGGER.debug(
            "Climate %s\n"
            "- _temp_sensor_device %s\n"
            "- _target_temp_device %s\n"
            "- _op_mode_device %s\n"
            "- _fan_mode_device %s",
            self.ha_id,
            self._temp_sensor_device.ha_id if self._temp_sensor_device else "None",
            self._target_temp_device.ha_id if self._target_temp_device else "None",
            self._op_mode_device.ha_id if self._op_mode_device else "None",
            self._fan_mode_device.ha_id if self._fan_mode_device else "None",
        )
        await super().async_added_to_hass()

        # Register update callback for child devices
        siblings = self.fibaro_device.fibaro_controller.get_siblings(self.fibaro_device)
        for device in siblings:
            if device != self.fibaro_device:
                self.controller.register(device.id, self._update_callback)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        if not self._fan_mode_device:
            return None
        return self._fan_support

    @property
    def fan_mode(self):
        """Return the fan setting."""
        if not self._fan_mode_device:
            return None
        mode = int(self._fan_mode_device.fibaro_device.properties.mode)
        return FANMODES[mode]

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if not self._fan_mode_device:
            return
        self._fan_mode_device.action("setFanMode", HA_FANMODES[fan_mode])

    @property
    def fibaro_op_mode(self):
        """Return the operating mode of the device."""
        if not self._op_mode_device:
            return 3  # Default to AUTO

        if "operatingMode" in self._op_mode_device.fibaro_device.properties:
            return int(self._op_mode_device.fibaro_device.properties.operatingMode)

        return int(self._op_mode_device.fibaro_device.properties.mode)

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return OPMODES_HVAC[self.fibaro_op_mode]

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        if not self._op_mode_device:
            return [HVAC_MODE_AUTO]  # Default to this
        return self._hvac_support

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        if not self._op_mode_device:
            return
        if self.preset_mode:
            return

        if "setOperatingMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action("setOperatingMode", HA_OPMODES_HVAC[hvac_mode])
        elif "setMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action("setMode", HA_OPMODES_HVAC[hvac_mode])

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        if not self._op_mode_device:
            return None

        if "operatingMode" in self._op_mode_device.fibaro_device.properties:
            mode = int(self._op_mode_device.fibaro_device.properties.operatingMode)
        else:
            mode = int(self._op_mode_device.fibaro_device.properties.mode)

        if mode not in OPMODES_PRESET:
            return None
        return OPMODES_PRESET[mode]

    @property
    def preset_modes(self):
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        if not self._op_mode_device:
            return None
        return self._preset_support

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._op_mode_device is None:
            return
        if "setOperatingMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action(
                "setOperatingMode", HA_OPMODES_PRESET[preset_mode]
            )
        elif "setMode" in self._op_mode_device.fibaro_device.actions:
            self._op_mode_device.action("setMode", HA_OPMODES_PRESET[preset_mode])

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_temp

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._temp_sensor_device:
            device = self._temp_sensor_device.fibaro_device
            if "heatingThermostatSetpoint" in device.properties:
                return float(device.properties.heatingThermostatSetpoint)
            return float(device.properties.value)
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._target_temp_device:
            device = self._target_temp_device.fibaro_device
            if "heatingThermostatSetpointFuture" in device.properties:
                return float(device.properties.heatingThermostatSetpointFuture)
            return float(device.properties.targetLevel)
        return None

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        target = self._target_temp_device
        if temperature is not None:
            if "setThermostatSetpoint" in target.fibaro_device.actions:
                target.action("setThermostatSetpoint", self.fibaro_op_mode, temperature)
            elif "setHeatingThermostatSetpoint" in target.fibaro_device.actions:
                target.action("setHeatingThermostatSetpoint", temperature)
            else:
                target.action("setTargetLevel", temperature)
