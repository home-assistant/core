"""Support for myIO thermostats."""
from datetime import timedelta
import logging

from myio.comms_thread import CommsThread  # pylint: disable=import-error

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import CONF_NAME, TEMP_CELSIUS
from homeassistant.util import slugify

from . import DOMAIN

# from homeassistant.components.myio_valet_mega.comms_thread import CommsThread

_LOGGER = logging.getLogger(__name__)
SUPPORT_FLAGS = 0
SCAN_INTERVAL = timedelta(seconds=5)
COMMS_THREAD = CommsThread()


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a climate entity from a config_entry."""

    _id = 0
    _server_name = slugify(config_entry.data[CONF_NAME])
    _server_status = hass.states.get(_server_name + ".state").state
    _server_data = hass.data[_server_name]
    _relays = _server_data["relays"]
    _pwms = _server_data["PWM"]
    _climate_entities = []

    if _server_status.startswith("Online"):
        # Check if any relay has a sensor controller, if it has add to the entities
        for _relay in _relays:
            if _relays[_relay]["sensor"] != 0:
                _id = _relays[_relay]["id"]
                _climate_entities.append(
                    MyIOThermostate(hass, config_entry, _id, _server_name)
                )
        # Check if any PWM output has a sensor controller, if it has add to the entities

        try:
            for _pwm in _pwms:
                _sensor = _pwms[_pwm]["sensor"]
                if _sensor != 0:
                    _id = _pwms[_pwm]["id"]
                    _climate_entities.append(
                        MyIOThermostate(hass, config_entry, _id, _server_name)
                    )
        except Exception as ex:
            _LOGGER.debug(
                "%s PWM doesn't have a sensor attribute - myIO-Server Version < 2.4.4.3",
                ex,
            )

        async_add_entities(_climate_entities, True)


class MyIOThermostate(ClimateDevice):
    """Implementation of a myIO-Server."""

    def __init__(self, hass, config_entry, _id, _server_name):
        """Initialize the sensor."""

        def id_converter(_eeprom_id):
            """Define Sensor ID by EEPROMID."""
            for _id in self._server_data["sensors"]:
                if self._server_data["sensors"][_id]["id"] == _eeprom_id:
                    return _id

        self._id = _id
        self.entity_id = f"climate.{_server_name}_{self._id}"
        self._config_entry = config_entry
        self._server_name = _server_name
        self._server_data = hass.data[_server_name]
        self._server_status = hass.states.get(_server_name + ".state").state

        """Decide if it is digital relay or PWM output."""
        if _id <= 64:
            self._output = "relays"
            self._id_mod = 1
        if _id >= 101:
            self._output = "PWM"
            self._id_mod = 101

        self._state = self._server_data[self._output][str(self._id - self._id_mod)][
            "state"
        ]
        self._name = self._server_data[self._output][str(self._id - self._id_mod)][
            "description"
        ]

        self._sensor = int(
            self._server_data[self._output][str(self._id - self._id_mod)]["sensor"]
        )
        if self._sensor <= 100:
            self._sensor = id_converter(_eeprom_id=self._sensor)

        self._sensor_on = (
            self._server_data[self._output][str(self._id - self._id_mod)]["sensorON"]
            / 10
        )
        self._sensor_off = (
            self._server_data[self._output][str(self._id - self._id_mod)]["sensorOFF"]
            / 10
        )

        """Set hvac_mode if it is in cool or heat mode."""
        self._hvac_modes = [HVAC_MODE_COOL, HVAC_MODE_HEAT]
        if self._sensor_off > self._sensor_on:
            self._hvac_mode = HVAC_MODE_HEAT
        else:
            self._hvac_mode = HVAC_MODE_COOL
        if self._hvac_mode == HVAC_MODE_HEAT:
            self._target_temperature_high = self._sensor_off
            self._target_temperature_low = self._sensor_on
            self._min_temp = (self._sensor_off + self._sensor_on) / 2 - (
                self._sensor_off - self._sensor_on
            )
            self._max_temp = (self._sensor_off + self._sensor_on) / 2 + (
                self._sensor_off - self._sensor_on
            )
            if self._min_temp + 1 > self._sensor_on:
                self._min_temp = self._sensor_on - 1
            if self._max_temp - 1 < self._sensor_off:
                self._max_temp = self._sensor_off + 1
        else:
            self._target_temperature_high = self._sensor_on
            self._target_temperature_low = self._sensor_off
            self._min_temp = (self._sensor_off + self._sensor_on) / 2 - (
                self._sensor_on - self._sensor_off
            )
            self._max_temp = (self._sensor_off + self._sensor_on) / 2 + (
                self._sensor_on - self._sensor_off
            )
        if self._state != 0 and self._hvac_mode == HVAC_MODE_HEAT:
            self._hvac_action = CURRENT_HVAC_HEAT
        if self._state != 0 and self._hvac_mode == HVAC_MODE_COOL:
            self._hvac_action = CURRENT_HVAC_COOL
        if self._state == 0:
            self._hvac_action = CURRENT_HVAC_IDLE
        if int(self._sensor) <= 100:
            self._unit_of_measurement = TEMP_CELSIUS
            self._target_temperature_step = 0.1
            self._precision = 0.1
            self._current_temperature = (
                self._server_data["sensors"][self._sensor]["temp"] / 100
            )
        elif int(self._sensor) <= 200:
            self._unit_of_measurement = TEMP_CELSIUS
            self._target_temperature_step = 1
            self._precision = 1
            self._current_temperature = (
                self._server_data["sensors"][str(self._sensor)]["hum"] / 10
            )
        # Initialize the climate device.
        self._unique_id = _id
        self._name = self._server_data[self._output][str(self._id - self._id_mod)][
            "description"
        ]
        # define SUPPORT_FLAGS
        self._support_flags = SUPPORT_FLAGS
        self._support_flags = self._support_flags | SUPPORT_TARGET_TEMPERATURE_RANGE

    @property
    def should_poll(self) -> bool:
        """No polling needed for a demo light."""
        return True

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._server_name, self._unique_id)
            },
            "name": self.name,
        }

    @property
    def scan_interval(self):
        """Return the unique id."""
        return SCAN_INTERVAL

    @property
    def unique_id(self):
        """Return the unique id."""
        return f"server name = {self._server_name}, id = {self._unique_id}"

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._target_temperature_high

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._target_temperature_low

    @property
    def max_temp(self):
        """Return the highbound target temperature we try to reach."""
        return self._max_temp

    @property
    def min_temp(self):
        """Return the lowbound target temperature we try to reach."""
        return self._min_temp

    @property
    def hvac_action(self):
        """Return current operation ie. heat, cool, idle."""
        return self._hvac_action

    @property
    def hvac_mode(self):
        """Return hvac target hvac state."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def precision(self):
        """Return the precision."""
        return self._precision

    @property
    def target_temperature_step(self):
        """Return the precision."""
        return self._target_temperature_step

    def server_status(self):
        """Return the server status."""
        return self.hass.states.get(f"{self._server_name}.state").state

    def server_data(self):
        """Return the server data dictionary database."""
        return self.hass.data[self._server_name]

    async def send_post(self, post):
        """Send post to the myIO-server, and apply the response."""
        [
            self.hass.data[self._server_name],
            self._server_status,
        ] = await COMMS_THREAD.send(
            server_data=self.server_data(),
            server_status=self.server_status(),
            config_entry=self._config_entry,
            _post=post,
        )
        self.hass.states.async_set(f"{self._server_name}.state", self._server_status)
        return True

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if (
            kwargs.get(ATTR_TARGET_TEMP_HIGH) is not None
            and kwargs.get(ATTR_TARGET_TEMP_LOW) is not None
        ):
            self._target_temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            self._target_temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
            _string_on = ""
            _string_off = ""
            if self._hvac_mode == HVAC_MODE_HEAT:
                if self._output == "relays":
                    _string_on = "min_temp_ON"
                    _string_off = "max_temp_OFF"
                else:
                    _string_on = "mix_temp_MIN"
                    _string_off = "mix_temp_MAX"
            else:
                if self._output == "relays":
                    _string_off = "min_temp_ON"
                    _string_on = "max_temp_OFF"
                else:
                    _string_off = "mix_temp_MIN"
                    _string_on = "mix_temp_MAX"
            await self.send_post(
                f"{_string_on}*{self._id-self._id_mod+1}="
                + f"{int(self._target_temperature_low*10)}&"
                + f"{_string_off}*{self._id-self._id_mod+1}="
                + f"{int(self._target_temperature_high*10)}"
            )
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""

        if self._output == "relays":
            await self.send_post(f"r_INV={self._id}")
        self.async_write_ha_state()

    async def async_update(self):
        """Fetch new state data for the sensor."""

        self._server_data = self.hass.data[self._server_name]
        if self._id <= 64:
            self._state = self._server_data[self._output][str(self._id - self._id_mod)][
                "state"
            ]
        if int(self._sensor) <= 100:
            self._current_temperature = (
                self._server_data["sensors"][self._sensor]["temp"] / 100
            )
        elif int(self._sensor) <= 200:
            self._current_temperature = (
                self._server_data["sensors"][str(self._sensor)]["hum"] / 10
            )
        if (
            self._server_data[self._output][str(self._id - self._id_mod)]["sensorOFF"]
            > self._server_data[self._output][str(self._id - self._id_mod)]["sensorON"]
        ):
            self._hvac_mode = HVAC_MODE_HEAT
        else:
            self._hvac_mode = HVAC_MODE_COOL
        if self._hvac_mode == HVAC_MODE_HEAT:
            self._target_temperature_low = (
                self._server_data[self._output][str(self._id - self._id_mod)][
                    "sensorON"
                ]
                / 10
            )
            self._target_temperature_high = (
                self._server_data[self._output][str(self._id - self._id_mod)][
                    "sensorOFF"
                ]
                / 10
            )
        if self._hvac_mode == HVAC_MODE_COOL:
            self._target_temperature_low = (
                self._server_data[self._output][str(self._id - self._id_mod)][
                    "sensorOFF"
                ]
                / 10
            )
            self._target_temperature_high = (
                self._server_data[self._output][str(self._id - self._id_mod)][
                    "sensorON"
                ]
                / 10
            )
        self._min_temp = (
            self._target_temperature_high + self._target_temperature_low
        ) / 2 - (self._target_temperature_high - self._target_temperature_low)
        self._max_temp = (
            self._target_temperature_high + self._target_temperature_low
        ) / 2 + (self._target_temperature_high - self._target_temperature_low)

        if self._min_temp + 1 > self._target_temperature_low:
            self._min_temp = self._target_temperature_low - 1
        if self._max_temp - 1 < self._target_temperature_high:
            self._max_temp = self._target_temperature_high + 1

        if self._state != 0 and self._hvac_mode == HVAC_MODE_HEAT:
            self._hvac_action = CURRENT_HVAC_HEAT
        if self._state != 0 and self._hvac_mode == HVAC_MODE_COOL:
            self._hvac_action = CURRENT_HVAC_COOL
        if self._state == 0:
            self._hvac_action = CURRENT_HVAC_IDLE

        self.schedule_update_ha_state()
