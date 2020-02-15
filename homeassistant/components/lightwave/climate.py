"""Support for LightwaveRF TRVs."""
import json
import logging
import socket

from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
    ClimateDevice,
)
from homeassistant.components.climate.const import CURRENT_HVAC_HEAT, CURRENT_HVAC_OFF
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, TEMP_CELSIUS

from . import LIGHTWAVE_LINK, LIGHTWAVE_TRV_PROXY, LIGHTWAVE_TRV_PROXY_PORT

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Find and return LightWave lights."""
    if not discovery_info:
        return

    trv = []
    lwlink = hass.data[LIGHTWAVE_LINK]
    trv_proxy_ip = hass.data[LIGHTWAVE_TRV_PROXY]
    trv_proxy_port = hass.data[LIGHTWAVE_TRV_PROXY_PORT]

    for device_id, device_config in discovery_info.items():
        name = device_config[CONF_NAME]
        serial = device_config["serial"]
        trv.append(
            LightwaveTrv(name, device_id, lwlink, serial, trv_proxy_ip, trv_proxy_port)
        )

    async_add_entities(trv)


class LightwaveTrv(ClimateDevice):
    """Representation of a LightWaveRF TRV."""

    def __init__(self, name, device_id, lwlink, serial, trv_proxy_ip, trv_proxy_port):
        """Initialize LightwaveTrv entity."""
        self._name = name
        self._device_id = device_id
        self._state = None
        self._max_temp = DEFAULT_MAX_TEMP
        self._min_temp = DEFAULT_MIN_TEMP
        self._current_temperature = None
        self._target_temperature = None
        self._temperature_unit = TEMP_CELSIUS
        self._target_temperature_step = 0.5
        self._hvac_mode = HVAC_MODE_HEAT
        self._hvac_action = None
        self._lwlink = lwlink
        self._battery = None
        self._serial = serial
        self._proxy_ip = trv_proxy_ip
        self._proxy_port = trv_proxy_port
        self._inhibit = 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def should_poll(self):
        """Poll the Proxy."""
        return True

    def update_ctarg(self, j):
        """Update target temp logic."""
        if self._inhibit == 0:
            self._target_temperature = j["cTarg"]
            if j["cTarg"] == 0:
                # TRV off
                self._target_temperature = None
            if j["cTarg"] >= 40:
                # Call for heat mode, or TRV in a fixed position
                self._target_temperature = None
        else:
            # Done the job - use proxy next iteration
            self._inhibit = 0

    def update(self):
        """Communicate with a Lightwave RTF Proxy to get state."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(2.0)
                msg = self._serial.encode("UTF-8")
                sock.sendto(msg, (self._proxy_ip, self._proxy_port))
                response, dummy = sock.recvfrom(1024)
                msg = response.decode()
                j = json.loads(msg)
                if "cTemp" in j.keys():
                    self._current_temperature = j["cTemp"]
                if "cTarg" in j.keys():
                    self.update_ctarg(j)
                if "batt" in j.keys():
                    # convert the voltage to a rough percentage
                    self._battery = int((j["batt"] - 2.22) * 110)
                if "output" in j.keys():
                    if int(j["output"]) > 0:
                        self._hvac_action = CURRENT_HVAC_HEAT
                    else:
                        self._hvac_action = CURRENT_HVAC_OFF
                if "error" in j.keys():
                    _LOGGER.warning("TRV proxy error: %s", j["error"])

        except socket.timeout:
            _LOGGER.warning("TRV proxy not responing")

        except socket.error as ex:
            _LOGGER.warning("TRV proxy error %s", ex)

        except json.JSONDecodeError:
            _LOGGER.warning("TRV proxy JSON error")

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            "Battery Level": self._battery,
            "Device Type": "LightwaveRF TRV",
        }

    @property
    def name(self):
        """Lightwave trv name."""
        return self._name

    @property
    def current_temperature(self):
        """Property giving the current room temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Target room temperature."""
        if self._inhibit > 0:
            # if we get an update before the new temp has
            # propagated, the GUI target temp is set back to the
            # old target, showing a false reading temporarily
            self._target_temperature = self._inhibit
        return self._target_temperature

    @property
    def hvac_modes(self):
        """HVAC modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def hvac_mode(self):
        """HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_action(self):
        """HVAC action."""
        return self._hvac_action

    @property
    def min_temp(self):
        """Min Temp."""
        return self._min_temp

    @property
    def max_temp(self):
        """Max Temp."""
        return self._max_temp

    @property
    def temperature_unit(self):
        """Set temperature unit."""
        return self._temperature_unit

    @property
    def target_temperature_step(self):
        """Set temperature step."""
        return self._target_temperature_step

    def set_temperature(self, **kwargs):
        """Set TRV target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._target_temperature = kwargs[ATTR_TEMPERATURE]
            self._inhibit = self._target_temperature
        self._lwlink.set_temperature(
            self._device_id, self._target_temperature, self._name
        )
        self.async_schedule_update_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC Mode for TRV."""
