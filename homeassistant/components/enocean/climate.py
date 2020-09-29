"""Support for Enocean Valve with integrated PID Controller."""

import logging

from enocean.protocol.constants import PACKET, RORG
from enocean.protocol.packet import RadioPacket
from simple_pid import PID
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    DOMAIN,
    HVAC_MODE_AUTO,
    HVAC_MODE_OFF,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_BATTERY_LEVEL, CONF_ID, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from .device import EnOceanEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "EnOcean Valve"

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

CONF_TARGET_TEMP = "target_temp"
CONF_SETPOINTSELECTION = "setpointselection"
CONF_PID_PARAMETER = "pid_parameter"

DEFAULT_PID_PARAMETER_KP = 0.5
DEFAULT_PID_PARAMETER_KI = 0.2
DEFAULT_PID_PARAMETER_KD = 0

SCHEMA_PID_PARAMETER = vol.Schema({"Kp": float, "Ki": float, "Kd": float})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SETPOINTSELECTION, default="pos"): cv.string,
        vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
        vol.Optional(
            CONF_PID_PARAMETER, default={"Kp": 0, "Ki": 0, "Kd": 0}
        ): SCHEMA_PID_PARAMETER
        # TODO: add offtemperature + other valid parameters
    }
)

ATTR_CURRENT_VALVEPOSITION = "valve_position"
ATTR_PID_OUTPUT = "pid_output"
ATTR_PID_PARA_KP = "pid_parameter_kp"
ATTR_PID_PARA_KI = "pid_parameter_ki"
ATTR_PID_PARA_KD = "pid_parameter_kd"

# TODO: add summer mode for battery saving for valves.
ATTR_MODE_SUMMER = "mode_summer"
DEFAULT_MODE_SUMMER = "Winter"
# TODO: set last transmission
# time since last data transmission (maybe used for timeout?)
ATTR_LAST_TRANSMISSION = "last_transmission"
_LOGGER.debug("logger test")


def setup_platform(hass, config, add_devices, add_entities, discovery_info=None):
    """Set up an EnOcean Valve device."""
    dev_id = config.get(CONF_ID)
    devname = config.get(CONF_NAME)
    target_temp = config.get(CONF_TARGET_TEMP)
    setpointSelection = config.get(CONF_SETPOINTSELECTION)
    pid_parameter = config.get(CONF_PID_PARAMETER)

    component = hass.data[DOMAIN]

    # TODO: add service "set_summer_mode". Summer mode for valves for
    # battery savings.

    component.async_register_entity_service(
        "set_pid_parameter",
        {
            vol.Optional(ATTR_PID_PARA_KP): vol.Coerce(float),
            vol.Optional(ATTR_PID_PARA_KI): vol.Coerce(float),
            vol.Optional(ATTR_PID_PARA_KD): vol.Coerce(float),
        },
        "async_set_pid_parameter",
    )

    _LOGGER.debug("pid parameter: %s", pid_parameter)

    add_devices(
        [
            EnOceanValve(
                hass, dev_id, devname, target_temp, setpointSelection, pid_parameter
            )
        ]
    )


class EnOceanValve(EnOceanEntity, ClimateEntity, RestoreEntity):
    # TODO: Add needed functions, scheduler, window open,...
    """Representation of an EnOcean valve actuator."""

    def __init__(
        self, hass, dev_id, devname, target_temp, setpointselection, pid_parameter
    ):
        """Initialize the EnOcean sensor device."""
        # import with "old enoComponent" name for compatibility
        # update to 0.95
        # enocean.EnOceanDevice.__init__(self)
        super().__init__(dev_id, devname)
        ClimateEntity.__init__(self)
        self.stype = "valve"
        self.dev_id = dev_id
        self.devname = devname
        self.eepProfile = "A5,20,01"
        self._unit = hass.config.units.temperature_unit
        self._cur_temp = 0
        self._support_flags = SUPPORT_FLAGS
        self._hvac_modes = [HVAC_MODE_AUTO, HVAC_MODE_OFF]
        self._hvac_mode = HVAC_MODE_AUTO
        self._cur_opening = 0  # current opening of the valve in %
        self.setpointselection = setpointselection
        self._battery_capacity = "OK"
        self._target_temp = target_temp
        # instantiate PID controller for valve
        self.pid_Kp = pid_parameter["Kp"]
        self.pid_Ki = pid_parameter["Ki"]
        self.pid_Kd = pid_parameter["Kd"]
        self.pid = PID(
            self.pid_Kp,
            self.pid_Ki,
            self.pid_Kd,
            setpoint=self._target_temp,
            sample_time=60,
            output_limits=(0, 100),
        )
        self._mode_summer = False
        self._last_transmission = 0
        self._hold_mode = None
        self._pid_output = 0

    # restore states at startup from db
    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._hvac_mode = old_state.state
            if old_state.attributes.get(ATTR_TEMPERATURE) is not None:
                self._target_temp = float(old_state.attributes.get(ATTR_TEMPERATURE))
            if old_state.attributes.get(ATTR_PID_PARA_KD) is not None:
                self.pid_Kp = float(old_state.attributes.get(ATTR_PID_PARA_KD))
            if old_state.attributes.get(ATTR_PID_PARA_KI) is not None:
                self.pid_Ki = float(old_state.attributes.get(ATTR_PID_PARA_KI))
            if old_state.attributes.get(ATTR_PID_PARA_KP) is not None:
                self.pid_Kp = float(old_state.attributes.get(ATTR_PID_PARA_KP))

            _LOGGER.debug(
                """restored old parameters.
                target temp:  %s, mode: %s
                PID Parameters: kd: %s, ki. %s, kp: %s""",
                self._target_temp,
                self._hvac_mode,
                self.pid_Kd,
                self.pid_Ki,
                self.pid_Kp,
            )

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        return {
            ATTR_CURRENT_VALVEPOSITION: self._cur_opening,
            ATTR_BATTERY_LEVEL: self._battery_capacity,
            ATTR_PID_OUTPUT: self._pid_output,
            ATTR_PID_PARA_KP: self.pid_Kp,
            ATTR_PID_PARA_KI: self.pid_Ki,
            ATTR_PID_PARA_KD: self.pid_Kd,
            ATTR_MODE_SUMMER: self._mode_summer,
            ATTR_LAST_TRANSMISSION: self._last_transmission,
        }

    @property
    def name(self):
        """Return the name of the device."""

        return self.devname

    def value_changed(self, enoceanPackage):
        """Update the internal state of the device."""
        _LOGGER.debug("Value changed, package in: %s", enoceanPackage)

        # send automatic teach in packet
        if enoceanPackage.packet_type != PACKET.RESPONSE and enoceanPackage.learn:
            _LOGGER.debug("lrn packet received")

            packet = RadioPacket.create(
                RORG.BS4,
                rorg_func=0x20,
                rorg_type=0x01,
                direction=2,
                destination=enoceanPackage.sender,
                learn=enoceanPackage.learn,
            )
            # sender is set in EnOceanDongle

            # copy EEP and manufacturer ID
            packet.data[1:5] = enoceanPackage.data[1:5]
            # update flags to acknowledge learn request
            packet.data[4] = 0xF0

            self.send_packet(packet)

        enoceanPackage.parse_eep(0x20, 0x01)

        try:
            self._cur_temp = enoceanPackage.parse()["TMP"].get("value")
            self._cur_opening = enoceanPackage.parse()["CV"].get("value")
            if enoceanPackage.parse()["BCAP"].get("value") == "false":
                self._battery_capacity = "LOW"
            if enoceanPackage.parse()["BCAP"].get("value") == "true":
                self._battery_capacity = "OK"
            _LOGGER.debug("Valve opening %s: %s", self.devname, self._cur_opening)

            for k in enoceanPackage.parse_eep(0x20, 0x01):
                _LOGGER.debug("{}: {}".format(k, enoceanPackage.parsed[k]))

        except KeyError:
            _LOGGER.warning("Key Error occurred")
            for k in enoceanPackage.parse_eep(0x20, 0x01):
                _LOGGER.warning("{}: {}".format(k, enoceanPackage.parsed[k]))

        if self._hvac_mode == HVAC_MODE_OFF:
            self._pid_output = 0
        if self._hvac_mode == HVAC_MODE_AUTO:
            # calculating the output for valve setpoint with pid controller
            self.calc_pid_output()

        temp_SP = 0

        if self._cur_temp < self._target_temp:
            temp_SP = 100

        # for the pid variant of the valve
        if self.setpointselection == "pid":
            temp_SP = self._pid_output

        setpoint_inversion = 0
        sps = 0

        if self.setpointselection == "temp":
            sps = 1
            temp_SP = round(self._pid_output / (40 / 255), 0)
            setpoint_inversion = 1

        out_packet = RadioPacket.create(
            RORG.BS4,
            rorg_func=0x20,
            rorg_type=0x01,
            direction=2,
            destination=self.dev_id,
            SPS=sps,
            SP=int(temp_SP),
            TMP=self._cur_temp,
            SPN=setpoint_inversion,
            LFS=0,
            RIN=0,
            RCU=0,
            learn=False,
        )
        # sender is set in EnoceanDongle

        # send answer
        self.send_packet(out_packet)

    def calc_pid_output(self):
        """Calculate the setpoint with a pid controller."""
        tempDiff = self._cur_temp - self._target_temp
        if self.pid_Kd == 0 and self.pid_Ki == 0 and self.pid_Kp == 0:
            if self._cur_temp < self._target_temp:
                self._pid_output = 40
            else:
                self._pid_output = 0
        else:
            # deadpoint
            if abs(tempDiff) < 0.25:
                self.pid.auto_mode = False
            if (abs(tempDiff) > 0.25) and (self.pid.auto_mode is False):
                self.pid.set_auto_mode(True, last_output=self._cur_temp)
            if abs(tempDiff) > 0.25:
                self._pid_output = self.pid(self._cur_temp)
            _LOGGER.debug("PID output: %s", self._pid_output)

    async def async_set_pid_parameter(self, **kwargs):
        """Set new pid parameter from service."""
        if kwargs.get(ATTR_PID_PARA_KP) is not None:
            self.pid_Kp = kwargs.get(ATTR_PID_PARA_KP)
            self.pid.Kp = self.pid_Kp
        if kwargs.get(ATTR_PID_PARA_KI) is not None:
            self.pid_Ki = kwargs.get(ATTR_PID_PARA_KI)
            self.pid.Ki = self.pid_Ki
        if kwargs.get(ATTR_PID_PARA_KD) is not None:
            self.pid_Kd = kwargs.get(ATTR_PID_PARA_KD)
            self.pid.Kd = self.pid_Kd
        _LOGGER.debug(
            "PID parameters set to: Kp:{}, Ki:{}, Kd:{}".format(
                self.pid_Kp, self.pid_Ki, self.pid_Kd
            )
        )

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._cur_temp

    @property
    def valve_position(self):
        """Return the actual valve position temperature."""
        return self._cur_opening

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        # return self._target_temp
        return self._target_temp

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            self._target_temp = new_temperature
            self.pid.setpoint = self._target_temp

    # @property
    # def _hvac_modes(self):
    #     """List of available operation modes."""
    #     return self._hvac_modes

    # @property
    # def current_operation(self):
    #     """Return current operation."""
    #     return self._hvac_mode

    # def set_operation_mode(self, operation_mode):
    #     """Set new Heating mode."""
    #     self._hvac_mode = operation_mode

    # def set_hold_mode(self, hold_mode):
    #     """Set new target hold mode."""
    #     return None

    # @property
    # def current_hold_mode(self):
    #     """Return the current hold mode, e.g., home, away, temp."""
    #     return None

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._support_flags

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return self._hvac_mode

    @property
    def hvac_modes(self) -> [str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_AUTO, HVAC_MODE_OFF]

    @property
    def hvac_action(self) -> str:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._cur_opening > 0:
            return CURRENT_HVAC_HEAT
        else:
            return CURRENT_HVAC_OFF

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            self._hvac_mode = HVAC_MODE_AUTO
        elif hvac_mode == HVAC_MODE_OFF:
            self._hvac_mode = HVAC_MODE_OFF

        # Ensure we update the current operation after changing the mode
        self.schedule_update_ha_state()

    @property
    def preset_modes(self) -> [str]:
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        return [PRESET_NONE, PRESET_HOME, PRESET_ECO]

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        # TODO: implement preset_modes
        return PRESET_NONE
