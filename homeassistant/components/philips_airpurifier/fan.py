"""Philips Air Purifier & Humidifier"""
import voluptuous as vol
import homeassistant.components.philips_airpurifier.airctrl as air
import homeassistant.helpers.config_validation as cv
from homeassistant.components.fan import FanEntity, PLATFORM_SCHEMA

__version__ = "0.1.0"

CONF_HOST = "host"
CONF_NAME = "name"
CONF_PROTOCOL = "protocol"

DEFAULT_NAME = "Philips AirPurifier"
DEFAULT_PROTOCOL = "1"
ICON = "mdi:air-purifier"

SPEED_LIST = [
    "Auto Mode",
    "Allergen Mode",
    "Sleep Mode",
    "Speed 1",
    "Speed 2",
    "Speed 3",
    "Turbo",
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): cv.string,
    }
)


### Setup Platform ###


def setup_platform(hass, config, add_devices, discovery_info=None):
    add_devices([PhilipsAirPurifierFan(hass, config)])


class PhilipsAirPurifierFan(FanEntity):
    def __init__(self, hass, config):
        self.hass = hass
        self._host = config[CONF_HOST]
        self._name = config[CONF_NAME]
        self._protocol = config[CONF_PROTOCOL]
        self._state = None
        self._session_key = None

        self._fan_speed = None

        self._pre_filter = None
        self._wick_filter = None
        self._carbon_filter = None
        self._hepa_filter = None

        self._pm25 = None
        self._humidity = None
        self._target_humidity = None
        self._allergen_index = None
        self._temperature = None
        self._function = None
        self._light_brightness = None
        self._used_index = None
        self._water_level = None
        self._child_lock = None

        if self._protocol == "1":
            self._client = air.AirClient(self._host)
            self._client.load_key()
        else:
            self._client = air.AirClient2(self._host)

        self.update()

    ### Update Fan attributes ###

    def _is_protocol_1(self):
        return self._protocol == "1"

    def _get_status(self):
        if self._is_protocol_1():
            url = "http://{}/di/v1/products/1/air".format(self._host)
            status = self._client.get(url)
        else:
            status = self._client.get()
        return status

    def _get_filter(self):
        if self._is_protocol_1():
            url = "http://{}/di/v1/products/1/fltsts".format(self._host)
            filters = self._client.get(url)
        else:
            filters = {}
            filters = self._client.get()
        return filters

    def update(self):
        filters = self._get_filter()
        self._pre_filter = filters["fltsts0"]
        if "wicksts" in filters:
            self._wick_filter = filters["wicksts"]
        self._carbon_filter = filters["fltsts2"]
        self._hepa_filter = filters["fltsts1"]

        status = self._get_status()
        if "pwr" in status:
            if status["pwr"] == "1":
                self._state = "on"
            else:
                self._state = "off"
        if "pm25" in status:
            self._pm25 = status["pm25"]
        if "rh" in status:
            self._humidity = status["rh"]
        if "rhset" in status:
            self._target_humidity = status["rhset"]
        if "iaql" in status:
            self._allergen_index = status["iaql"]
        if "temp" in status:
            self._temperature = status["temp"]
        if "func" in status:
            func = status["func"]
            func_str = {"P": "Purification", "PH": "Purification & Humidification"}
            self._function = func_str.get(func, func)
        if "mode" in status:
            mode = status["mode"]
            mode_str = {
                "P": "Auto Mode",
                "A": "Allergen Mode",
                "S": "Sleep Mode",
                "M": "Manual",
                "B": "Bacteria",
                "N": "Night",
            }
            self._fan_speed = mode_str.get(mode, mode)
        if "om" in status:
            om = status["om"]
            om_str = {
                "s": "Silent",
                "t": "Turbo",
                "1": "Speed 1",
                "2": "Speed 2",
                "3": "Speed 3",
            }
            om = om_str.get(om, om)
            if om != "Silent" and self._fan_speed == "Manual":
                self._fan_speed = om
        if "aqil" in status:
            self._light_brightness = status["aqil"]
        if "ddp" in status:
            ddp = status["ddp"]
            if self._is_protocol_1():
                ddp_str = {"0": "PM2.5", "1": "IAI"}
            else:
                ddp_str = {"0": "IAI", "1": "PM2.5", "3": "Humidity"}
            self._used_index = ddp_str.get(ddp, ddp)
        if "wl" in status:
            self._water_level = status["wl"]
        if "cl" in status:
            self._child_lock = status["cl"]

    ### Properties ###

    @property
    def state(self):
        return self._state

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return ICON

    @property
    def speed_list(self) -> list:
        return SPEED_LIST

    @property
    def speed(self) -> str:
        return self._fan_speed

    def turn_on(self, speed: str = None, **kwargs) -> None:
        if speed is None:
            values = {}
            values["pwr"] = "1"
            self._client.set_values(values)
        else:
            self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        values = {}
        values["pwr"] = "0"
        self._client.set_values(values)

    def set_speed(self, speed: str):
        values = {}
        if speed == "Turbo":
            values["om"] = "t"
        elif speed == "Speed 1":
            values["om"] = "1"
        elif speed == "Speed 2":
            values["om"] = "2"
        elif speed == "Speed 3":
            values["om"] = "3"
        elif speed == "Auto Mode":
            values["mode"] = "P"
        elif speed == "Allergen Mode":
            values["mode"] = "A"
        elif speed == "Sleep Mode":
            values["mode"] = "S"
        self._client.set_values(values)

    @property
    def device_state_attributes(self):
        attr = {}
        if self._function is not None:
            attr["function"] = self._function
        if self._used_index is not None:
            attr["used_index"] = self._used_index
        if self._pm25 is not None:
            attr["pm25"] = self._pm25
        if self._allergen_index is not None:
            attr["allergen_index"] = self._allergen_index
        if self._temperature is not None:
            attr["temperature"] = self._temperature
        if self._humidity is not None:
            attr["humidity"] = self._humidity
        if self._target_humidity is not None:
            attr["target_humidity"] = self._target_humidity
        if self._water_level is not None:
            attr["water_level"] = self._water_level
        if self._light_brightness is not None:
            attr["light_brightness"] = self._light_brightness
        if self._child_lock is not None:
            attr["child_lock"] = self._child_lock
        if self._pre_filter is not None:
            attr["pre_filter"] = self._pre_filter
        if self._wick_filter is not None:
            attr["wick_filter"] = self._wick_filter
        if self._carbon_filter is not None:
            attr["carbon_filter"] = self._carbon_filter
        if self._hepa_filter is not None:
            attr["hepa_filter"] = self._hepa_filter
        return attr
