import requests
from bs4 import BeautifulSoup
import datetime
import json
import math
import pprint

GLOBAL_LOGIN_ATTEMPTS = 4
global_login_attempts_left = GLOBAL_LOGIN_ATTEMPTS


class NexiaThermostat:

    ROOT_URL = "https://www.mynexia.com"
    AUTH_FAILED_STRING = "https://www.mynexia.com/login"
    AUTH_FORGOTTEN_PASSWORD_STRING = "https://www.mynexia.com/account/forgotten_credentials"
    UPDATE_RATE = 300  # 5 minutes

    HOLD_PERMANENT = "permanent"
    HOLD_DURATION = "duration"
    HOLD_RESUME_SCHEDULE = "schedule"

    FAN_MODE_AUTO = "auto"
    FAN_MODE_ON = "on"
    FAN_MODE_CIRCULATE = "circulate"
    FAN_MODES = [FAN_MODE_AUTO, FAN_MODE_ON, FAN_MODE_CIRCULATE]

    OPERATION_MODE_AUTO = "AUTO"
    OPERATION_MODE_COOL = "COOL"
    OPERATION_MODE_HEAT = "HEAT"
    OPERATION_MODE_OFF = "OFF"
    OPERATION_MODES = [OPERATION_MODE_AUTO, OPERATION_MODE_COOL, OPERATION_MODE_HEAT, OPERATION_MODE_OFF]

    PRESET_MODE_HOME = "home"
    PRESET_MODE_AWAY = "away"
    PRESET_MODE_SLEEP = "sleep"
    PRESET_MODES = [PRESET_MODE_HOME, PRESET_MODE_AWAY, PRESET_MODE_SLEEP]

    DAMPER_MODE_OPEN = 'Damper Open'
    DAMPER_MODE_CLOSED = 'Damper Closed'

    STATUS_COOL = "COOL"
    STATUS_HEAT = "HEAT"

    AIR_CLEANER_MODE_AUTO = "auto"
    AIR_CLEANER_MODE_QUICK = "quick"
    AIR_CLEANER_MODE_ALLERGY = "allergy"
    AIR_CLEANER_MODES = [AIR_CLEANER_MODE_AUTO, AIR_CLEANER_MODE_QUICK, AIR_CLEANER_MODE_ALLERGY]

    HUMIDITY_MIN = 0.35
    HUMIDITY_MAX = 0.65

    def __init__(self, house_id: int, username=None, password=None, auto_login=True, update_rate=None):
        """
        Connects to and provides the ability to get and set parameters of your Nexia connected thermostat.

        :param house_id: int - Your house_id. You can get this from logging in and looking at the url once you're
        looking at your climate device. https://www.mynexia.com/houses/<house_id>/climate
        :param username: str - Your login email address
        :param password: str - Your login password
        :param auto_login: bool - Default is True, Login now (True), or login manually later (False)
        :param update_rate: int - How many seconds between requesting a new JSON update. Default is 300s.
        """

        self.username = username
        self.password = password
        self.house_id = house_id
        self.last_csrf = None
        self.thermostat_json = None
        self.last_update = None

        # Control the update rate
        if update_rate is None:
            self.update_rate = datetime.timedelta(seconds=self.UPDATE_RATE)
        else:
            self.update_rate = datetime.timedelta(seconds=update_rate)

        # Create a session
        self.session = requests.session()
        self.session.max_redirects = 3

        # Login if requested
        if auto_login:
            self.login()

    def _get_authenticity_token(self, url: str):
        """
        Returns the csrf param and token.
        :param url: str
        :return: dict with "token" and "param" keys
        """
        r = self._get_url(url)
        self._check_response("Failed to get authenticity token", r)
        soup = BeautifulSoup(r.text, 'html5lib')
        param = soup.find("meta", attrs={'name': "csrf-param"})
        token = soup.find("meta", attrs={'name': "csrf-token"})
        if token and param:
            return {
                "token": token['content'],
                "param": param['content']
            }

    def _put_url(self, url: str, payload: dict):
        """
        Puts data from the session
        :param url: str
        :param payload: dict
        :return: response
        """
        request_url = self.ROOT_URL + url

        if not self.last_csrf:
            self.login()

        headers = {
            "X-CSRF-Token": self.last_csrf,
            "X-Requested-With": "XMLHttpRequest"
        }
        # Let the code throw the exception
        # try:
        #     r = self.session.put(request_url, payload, headers=headers, allow_redirects=False)
        # except requests.RequestException as e:
        #     print("Error putting url", str(e))
        #     return None
        r = self.session.put(request_url, payload, headers=headers, allow_redirects=False)

        if r.status_code == 302:
            # assuming its redirecting to login
            self.login()
            r = self._put_url(url, payload)

        self._check_response(f"Failed PUT Request:\n  Url: {url}\n  Payload {payload}", r)

        # Assume something change, so update the thermostat's JSON
        self.update()

        return r

    def _post_url(self, url: str, payload: dict):
        """
        Posts data to the session from the url and payload
        :param url: str
        :param payload: dict
        :return: response
        """
        request_url = self.ROOT_URL + url

        # Let the code throw the exception
        # try:
        #     r = self.session.post(request_url, payload)
        # except requests.RequestException as e:
        #     print("Error posting url", str(e))
        #     return None
        r = self.session.post(request_url, payload)

        if r.status_code == 302:
            # assuming its redirecting to login
            self.login()
            return self._post_url(url, payload)

        # Assume something changed, so update the thermostat's JSON
        self.update()

        self._check_response("Failed to POST url", r)
        return r

    def _get_url(self, url):
        """
        Returns the full session.get from the URL (ROOT_URL + url)
        :param url: str
        :return: response
        """
        request_url = self.ROOT_URL + url

        # Let the code throw the exception
        # try:
        #     r = self.session.get(request_url, allow_redirects=False)
        # except requests.RequestException as e:
        #     print("Error getting url", str(e))
        #     return None
        r = self.session.get(request_url, allow_redirects=False)

        if r.status_code == 302:
            # assuming its redirecting to login
            self.login()
            return self._get_url(url)

        self._check_response("Failed to GET url", r)
        return r

    @staticmethod
    def _check_response(error_text, r):
        """
        Checks the request response, throws exception with the description text
        :param error_text: str
        :param r: response
        :return: None
        """
        if r is None or r.status_code != 200:
            if r is not None:
                response = ""
                for key in r.__attrs__:
                    response += f"  {key}: {getattr(r, key)}\n"
                raise Exception(f"{error_text}\n{response}")
            else:
                raise Exception(f"No response from session. {error_text}")

    def _needs_update(self):
        """
        Returns True if an update is needed
        :return: bool
        """
        if self.last_update is None:
            return True
        else:
            return datetime.datetime.now() - self.last_update > self.update_rate

    def _get_thermostat_json(self):
        """
        Returns the thermostat's JSON data. It's either cached, or returned directly from the internet
        :return: dict(thermostat_jason)
        """
        if self.thermostat_json is None or self._needs_update():
            r = self._get_url("/houses/" + str(self.house_id) + "/xxl_thermostats")
            if r and r.status_code == 200:
                ts = json.loads(r.text)
                if len(ts):
                    self.thermostat_json = ts[0]
                    self.last_update = datetime.datetime.now()
                else:
                    raise Exception("Nothing in the JSON")
            else:
                self._check_response("Failed to get thermostat JSON, session probably timed out", r)
        return self.thermostat_json

    def _get_thermostat_key(self, key):
        """
        Returns the thermostat value from the provided key in the thermostat's JSON.
        :param key: str
        :return: value
        """
        thermostat = self._get_thermostat_json()
        if thermostat and key in thermostat:
            return thermostat[key]
        raise KeyError(f"Key \"{key}\" not in the thermostat JSON!")

    def _get_thermostat_put_url(self, text=None):
        """
        Returns the PUT url from the text parameter
        :param text: str
        :return: str
        """
        return "/houses/" + str(self.house_id) + "/xxl_thermostats/" + str(self.get_thermostat_device_id()) + \
               ("/" + text if text else "")

    def _get_zone_json(self, zone_id=0):
        """
        Returns the thermostat zone's JSON
        :param zone_id: The index of the zone, defaults to 0.
        :return: dict(thermostat_json['zones'][zone_id])
        """
        thermostat = self._get_thermostat_json()
        if not thermostat:
            return None

        if len(thermostat['zones']) > zone_id:
            return thermostat['zones'][zone_id]

        raise IndexError(f"The zone_id ({zone_id}) does not exist in the thermostat zones.")

    def _get_zone_key(self, key, zone_id=0):
        """
        Returns the zone value for the key and zone_id provided.
        :param key: str
        :param zone_id: The index of the zone, defaults to 0.
        :return: The value of the key/value pair.
        """
        zone = self._get_zone_json(zone_id)
        if key in zone:
            return zone[key]

        raise KeyError(f"Zone {zone_id} key \"{key}\" invalid.")

    def _get_zone_put_url(self, text=None, zone_id=0):
        """
        Returns the PUT url from the text parameter for a specific zone
        :param text: str
        :param zone_id: The index of the zone, defaults to 0.

        :return: str
        """
        zone_id = self._get_zone_key('id', zone_id)
        return "/houses/" + str(self.house_id) + "/xxl_zones/" + str(zone_id) + ("/" + text if text else "")

    ########################################################################
    # Session Methods

    def login(self):
        """
        Provides you with a Nexia web session.

        All parameters should be set prior to calling this.
        - username - (str) Your email addres
        - password - (str) Your login password
        - house_id - (int) Your house id
        :return: None
        """
        global GLOBAL_LOGIN_ATTEMPTS, global_login_attempts_left
        if global_login_attempts_left > 0:
            token = self._get_authenticity_token("/login")
            if token:
                payload = {
                    'login': self.username,
                    'password': self.password,
                    token['param']: token['token']
                }
                self.last_csrf = token['token']

                r = self._post_url("/session", payload)

                if r is None or r.status_code != 200 and r.status_code != 302:
                    global_login_attempts_left -= 1
                self._check_response("Failed to login", r)

                if r.url == self.AUTH_FORGOTTEN_PASSWORD_STRING:
                    raise Exception(f"Failed to login, getting redirected to {r.url}. Try to login manually on the "
                                    f"website.")

            else:
                raise Exception("Failed to get csrf token")
        else:
            raise Exception(f"Failed to login after {GLOBAL_LOGIN_ATTEMPTS} attempts! Any more attempts may lock your "
                            f"account!")

    def get_last_update(self):
        """
        Returns a string indicating the ISO formatted time string of the last update
        :return: The ISO formatted time string of the last update
        """
        if self.last_update is None:
            return "Never"
        else:
            return datetime.datetime.isoformat(self.last_update)

    def update(self):
        """
        Forces a status update
        :return: None
        """
        self.thermostat_json = None
        self._get_thermostat_json()

    ########################################################################
    # Print Functions

    def print_thermostat_data(self):
        """
        Prints just the thermostat data, no zone data
        :return: None
        """
        thermostat_json = self._get_thermostat_json().copy()
        thermostat_json.pop("zones")
        pprint.pprint(thermostat_json)

    def print_zone_data(self, zone_id):
        """
        Prints the specified zone data
        :param zone_id:
        :return: None
        """
        thermostat_json = self._get_zone_json(zone_id)
        pprint.pprint(thermostat_json)

    def print_all_json_data(self):
        """
        Prints all zone data
        :return: None
        """
        thermostat_json = self._get_thermostat_json()
        pprint.pprint(thermostat_json)

    ########################################################################
    # Thermostat Attributes

    def get_thermostat_model(self):
        """
        Returns the thermostat model
        :return: string
        """
        return self._get_thermostat_key("model_number")

    def get_thermostat_firmware(self):
        """
        Returns the thermostat firmware version
        :return: string
        """
        return self._get_thermostat_key("firmware_build_name")

    def get_thermostat_dev_build_number(self):
        """
        Returns the thermostat development build number.
        :return: string
        """
        return self._get_thermostat_key("dev_build_number")

    def get_thermostat_device_id(self):
        """
        Returns the device id
        :return: string
        """
        return self._get_thermostat_key("id")

    def get_thermostat_house_id(self):
        """
        Returns the thermostat house id
        :return: str
        """
        return self._get_thermostat_key("house_id")

    def get_thermostat_dealer_id(self):
        """
        Returns the thermostat dealer id (phone number)
        :return: str
        """
        return self._get_thermostat_key("dealer_identifier")

    def get_thermostat_type(self):
        """
        Returns the thermostat type, such as TraneXl1050
        :return: str
        """
        return self._get_thermostat_key("type")

    def get_thermostat_name(self):
        """
        Returns the name of the thermostat. This is not the zone name.
        :return: str
        """
        return self._get_thermostat_key("name")

    ########################################################################
    # Supported Features

    def has_outdoor_temperature(self):
        """
        Capability indication of whether the thermostat has an outdoor temperature sensor
        :return: bool
        """
        return self._get_thermostat_key("have_odt")

    def has_relative_humidity(self):
        """
        Capability indication of whether the thermostat has an relative humidity sensor
        :return: bool
        """
        return self._get_thermostat_key("have_rh")

    def has_variable_speed_compressor(self):
        """
        Capability indication of whether the thermostat has a variable speed compressor
        :return: bool
        """
        return self._get_thermostat_key("has_variable_speed_compressor")

    def has_emergency_heat(self):
        """
        Capability indication of whether the thermostat has emergency/aux heat.
        :return: bool
        """
        return self._get_thermostat_key("emergency_heat_supported")

    def has_variable_fan_speed(self):
        """
        Capability indication of whether the thermostat has a variable speed blower
        :return: bool
        """
        return self._get_thermostat_key("fan_type") == "VSPD"

    ########################################################################
    # System Attributes

    def get_deadband(self):
        """
        Returns the deadband of the thermostat. This is the minimum number of degrees between the heat and cool
        setpoints in the number of degrees in the temperature unit selected by the thermostat.
        :return: int
        """
        return self._get_thermostat_key("temperature_deadband")

    def get_setpoint_limits(self):
        """
        Returns a tuple of the minimum and maximum temperature that can be set on any zone. This is in the temperature
        unit selected by the thermostat.
        :return: (int, int)
        """
        return self._get_thermostat_key("temperature_low_limit"), self._get_thermostat_key("temperature_high_limit")

    def get_variable_fan_speed_limits(self):
        """
        Returns the variable fan speed setpoint limits of the thermostat.
        :return: (float, float)
        """
        if self.has_variable_fan_speed:
            return self._get_thermostat_key("min_fan_speed"), self._get_thermostat_key("max_fan_speed")
        else:
            raise AttributeError("This thermostat does not support fan speeds")

    def get_unit(self):
        """
        Returns the temperature unit used by this system, either C or F.
        :return: str
        """
        return self._get_thermostat_key("scale").upper()

    def get_humidity_setpoint_limits(self):
        """
        Returns the humidity setpoint limits of the thermostat.

        This is a hard-set limit in this code that I believe is universal to all TraneXl thermostats.
        :return: (float, float)
        """
        return self.HUMIDITY_MIN, self.HUMIDITY_MAX

    ########################################################################
    # System Universal Boolean Get Methods

    def is_blower_active(self):
        """
        Returns True if the blower is active
        :return: bool
        """
        return self._get_thermostat_key("blower_active")

    def is_emergency_heat_active(self):
        """
        Returns True if the emergency/aux heat is active
        :return: bool
        """
        if self.has_emergency_heat():
            return self._get_thermostat_key("emergency_heat_active")
        else:
            raise Exception("This system does not support emergency heat")

    ########################################################################
    # System Universal Get Methods

    def get_fan_mode(self):
        """
        Returns the current fan mode. See FAN_MODES for the available options.
        :return: str
        """
        return self._get_thermostat_key('fan_mode')

    def get_outdoor_temperature(self):
        """
        Returns the outdoor temperature.
        :return:
        """
        if self.has_outdoor_temperature():
            return self._get_thermostat_key('outdoor_temperature')
        else:
            raise Exception("This system does not have an outdoor temperature sensor")

    def get_relative_humidity(self):
        """
        Returns the indoor relative humidity as a percent (0-1)
        :return: float
        """
        if self.has_relative_humidity():
            return self._get_thermostat_key("current_relative_humidity")
        else:
            raise Exception("This system does not have a relative humidity sensor.")

    def get_compressor_speed(self):
        """
        Returns the variable compressor speed, if supported, as a percent (0-1)
        :return: float
        """
        if self.has_variable_speed_compressor():
            return self._get_thermostat_key("compressor_speed")
        else:
            raise Exception("This system does not have a variable speed compressor.")

    def get_fan_speed_setpoint(self):
        """
        Returns the current variable fan speed setpoint from 0-1.
        :return: float
        """
        if self.has_variable_fan_speed():
            return self._get_thermostat_key("fan_speed")
        else:
            raise AttributeError("This system does not have variable fan speed.")

    def get_dehumidify_setpoint(self):
        """
        Returns the dehumidify setpoint from 0-1
        :return: float
        """
        return self._get_thermostat_key('dehumidify_setpoint')

    ########################################################################
    # System Universal Set Methods

    def set_fan_mode(self, fan_mode: str):
        """
        Sets the fan mode.
        :param fan_mode: string that must be in NexiaThermostat.FAN_MODES
        :return: None
        """
        fan_mode = fan_mode.lower()
        if fan_mode in self.FAN_MODES:
            url = self._get_thermostat_put_url("fan_mode")
            data = {"fan_mode": fan_mode}
            self._put_url(url, data)
        else:
            raise KeyError("Invalid fan mode specified")

    # TODO: Figure out what the PUT url is... I can't seem to set the fan speed from the website, but the capability
    #       exists in the Nexia app for iOS.
    # def set_fan_setpoint(self, fan_setpoint: float):
    #     """
    #     Sets the fan's setpoint speed as a percent in range. You can see the limits by calling
    #     Nexia.get_variable_fan_speed_limits()
    #     :param fan_setpoint: float
    #     :return: None
    #     """
    #
    #     # This call will get the limits, as well as check if this system has a variable speed fan
    #     min_speed, max_speed = self.get_variable_fan_speed_limits()
    #
    #     if min_speed <= fan_setpoint <= max_speed:
    #         url = self._get_thermostat_put_url("?????")
    #         data = {"fan_mode": self.get_fan_mode(), "fan_speed": fan_setpoint}
    #         self._put_url(url, data)
    #     else:
    #         raise ValueError(f"The fan setpoint, {fan_setpoint} is not between {min_speed} and {max_speed}.")

    def set_air_cleaner(self, air_cleaner_mode: str):
        """
        Sets the air cleaner mode.
        :param air_cleaner_mode: string that must be in NexiaThermostat.AIR_CLEANER_MODES
        :return: None
        """
        air_cleaner_mode = air_cleaner_mode.lower()
        if air_cleaner_mode in self.AIR_CLEANER_MODES:
            url = self._get_thermostat_put_url("air_cleaner_mode")
            data = {"air_cleaner_mode": air_cleaner_mode}
            self._put_url(url, data)
        else:
            raise KeyError("Invalid air cleaner mode specified")

    def set_follow_schedule(self, follow_schedule):
        """
        Enables or disables scheduled operation
        :param follow_schedule: bool - True for follow schedule, False for hold current setpoints
        :return: None
        """
        url = self._get_thermostat_put_url("scheduling_enabled")
        data = {"scheduling_enabled": "enabled" if follow_schedule else "disabled"}
        self._put_url(url, data)

    def set_emergency_heat(self, emergency_heat_on):
        """
        Enables or disables emergency / auxillary heat.
        :param emergency_heat_on: bool - True for enabled, False for Disabled
        :return: None
        """
        if self.has_emergency_heat():
            url = self._get_thermostat_put_url("emergency_heat")
            data = {"emergency_heat_active": True if emergency_heat_on else False}
            self._put_url(url, data)
        else:
            raise Exception("This thermostat does not support emergency heat.")

    def set_dehumidify_setpoint(self, dehumidify_setpoint):
        """
        Sets the overall system's dehumidify setpoint as a percent (0-1).

        The system must support
        :param dehumidify_setpoint: float
        :return: None
        """
        if self.has_relative_humidity():
            (min_humidity, max_humidity) = self.get_humidity_setpoint_limits()

            if min_humidity <= dehumidify_setpoint <= max_humidity:
                url = self._get_thermostat_put_url("humidity_setpoints")
                data = {"dehumidify_setpoint": dehumidify_setpoint,
                        "dehumidify_allowed": True,
                        "id": self.get_thermostat_device_id(),
                        "humidify_setpoint": 0.50,
                        "humidify_allowed": False}
                self._put_url(url, data)
            else:
                raise ValueError(f"humidity_level out of range ({min_humidity} - {max_humidity})")
        else:
            raise Exception("Setting target humidity is not supported on this thermostat.")

    # TODO - Do any system's actually support humidifying? I.e. putting moisture into a controlled space?

    ########################################################################
    # Zone Get Methods

    def get_zone_ids(self):
        """
        Returns a list of available zone IDs with a starting index of 0.
        :return: list(int)
        """
        # The zones are in a list, so there are no keys to pull out. I have to create a new list of IDs.
        return list(range(len(self._get_thermostat_key("zones"))))

    def get_zone_name(self, zone_id=0):
        """
        Returns the zone name
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return self._get_zone_key("name", zone_id=zone_id)

    def get_zone_cooling_setpoint(self, zone_id=0):
        """
        Returns the cooling setpoint in the temperature unit of the thermostat
        :param zone_id: The index of the zone, defaults to 0.
        :return: int
        """
        return self._get_zone_key('cooling_setpoint', zone_id=zone_id)

    def get_zone_heating_setpoint(self, zone_id=0):
        """
        Returns the heating setpoint in the temperature unit of the thermostat
        :param zone_id: The index of the zone, defaults to 0.
        :return: int
        """
        return self._get_zone_key('heating_setpoint', zone_id=zone_id)

    def get_zone_current_mode(self, zone_id=0):
        """
        Returns the current mode of the zone. This may not match the requested mode
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return self._get_zone_key("last_zone_mode", zone_id=zone_id).upper()

    def get_zone_requested_mode(self, zone_id=0):
        """
        Returns the requested mode of the zone. This should match the zone's mode on the thermostat. Available options
        can be found in NexiaThermostat.OPERATION_MODES
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return self._get_zone_key("requested_zone_mode", zone_id=zone_id).upper()

    def get_zone_temperature(self, zone_id=0):
        """
        Returns the temperature of the zone in the temperature unit of the thermostat.
        :param zone_id: The index of the zone, defaults to 0.
        :return: int
        """
        return self._get_zone_key('temperature', zone_id=zone_id)

    def get_zone_presets(self, zone_id=0):
        """
        Supposed to return the zone presets. For some reason, most of the time, my unit only returns "AWAY", but I can
        set the other modes. There is the capability to add additional zone presets on the main thermostat, so this
        may not work as expected.

        TODO: Try to get this working more reliably
        :param zone_id: int - Doesn't do anything as of the current implementation
        :return:
        """
        # return self._get_zone_key("presets", zone_id=zone_id)
        # Can't get Nexia to return all of the presets occasionally, but I don't think there would be any other
        # "presets" available anyway...
        return self.PRESET_MODES

    def get_zone_preset(self, zone_id=0):
        """
        Returns the zone's currently selected preset. Should be one of the strings in
        NexiaThermostat.get_zone_presets(zone_id).
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return self._get_zone_key("preset_selected", zone_id=zone_id)

    def get_zone_preset_setpoints(self, preset, zone_id=0):
        """
        Returns the setpoints of the provided preset in the zone provided.
        :param preset: str - The preset to get the setpoints from
        :param zone_id: The index of the zone, defaults to 0.
        :return: (int, int)
        """
        index = self.get_zone_presets(zone_id).index(preset) + 1
        return(self._get_zone_key(f"preset_cool{index}", zone_id=zone_id),
               self._get_zone_key(f"preset_heat{index}", zone_id=zone_id))

    def get_zone_status(self, zone_id=0):
        """
        Seems to mainly return the zone's damper status. I found if it returned an empty string, that the Nexia app
        would show that the damper was closed, so I'm taking a broad assumption that this is the case.
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        status = self._get_zone_key("zone_status", zone_id=zone_id)
        if len(status):
            return status
        else:
            return "Damper Closed"

    def check_heat_cool_setpoints(self, heat_temperature=None, cool_temperature=None):
        """
        Checks the heat and cool setpoints to check if they are within the appropriate range and within the deadband
        limits.

        Will throw exception if not valid.
        :param heat_temperature: int
        :param cool_temperature: int
        :return: None
        """

        deadband = self.get_deadband()
        (min_temperature, max_temperature) = self.get_setpoint_limits()

        if heat_temperature is not None:
            heat_temperature = int(heat_temperature)
        if cool_temperature is not None:
            cool_temperature = int(cool_temperature)

        if heat_temperature is not None and cool_temperature is not None and not heat_temperature < cool_temperature:
            raise AttributeError(f"The heat setpoint ({heat_temperature}) must be less than the cool setpoint "
                                 f"({cool_temperature}).")
        elif heat_temperature is not None and cool_temperature is not None and \
                not cool_temperature - heat_temperature >= deadband:
            raise AttributeError(f"The heat and cool setpoints must be at least {deadband} degrees different.")
        elif heat_temperature is not None and not heat_temperature <= max_temperature:
            raise AttributeError(f"The heat setpoint ({heat_temperature} must be less than the maximum temperature of "
                                 f"{max_temperature} degrees.")
        elif cool_temperature is not None and not cool_temperature >= min_temperature:
            raise AttributeError(f"The cool setpoint ({cool_temperature}) must be greater than the minimum temperature "
                                 f"of {min_temperature} degrees.")
        else:
            # The heat and cool setpoints appear to be valid.
            return

    ########################################################################
    # Zone Set Methods

    def call_return_to_schedule(self, zone_id=0):
        """
        Tells the zone to return to its schedule.
        :param zone_id: The index of the zone, defaults to 0.
        :return: None
        """

        # Set the thermostat
        url = self._get_zone_put_url("return_to_schedule", zone_id)
        data = {}
        self._put_url(url, data)

    def call_permanent_hold(self, heat_temperature=None, cool_temperature=None, zone_id=0):
        """
        Tells the zone to call a permanent hold. Optionally can provide the temperatures.
        :param heat_temperature:
        :param cool_temperature:
        :param zone_id: The index of the zone, defaults to 0.
        :return:
        """

        if heat_temperature is None and cool_temperature is None:
            # Just calling permanent hold on the current temperature
            heat_temperature = self.get_zone_heating_setpoint(zone_id)
            cool_temperature = self.get_zone_cooling_setpoint(zone_id)
        elif heat_temperature is not None and cool_temperature is not None:
            # Both heat and cool setpoints provided, continue
            pass
        else:
            # Not sure how I want to handle only one temperature provided, but this definitely assumes you're using
            # auto mode.
            raise AttributeError("Must either provide both heat and cool setpoints, or don't provide either")

        # Check that the setpoints are valid
        self.check_heat_cool_setpoints(heat_temperature, cool_temperature)

        # Set the thermostat
        url = self._get_zone_put_url("permanent_hold", zone_id)
        data = {
            "hold_cooling_setpoint": cool_temperature,
            "hold_heating_setpoint": heat_temperature,
            'cooling_setpoint': cool_temperature,
            'cooling_integer': str(cool_temperature),
            'heating_setpoint': heat_temperature,
            'heating_integer': str(heat_temperature),
            "hold_time": 0,
            "permanent_hold": True
        }
        self._put_url(url, data)

    def call_temporary_hold(self, heat_temperature=None, cool_temperature=None, holdtime=0, zone_id=0):
        """
        Call a temporary hold. If the holdtime is 0, it will simply hold until the next scheduled time.
        :param heat_temperature: int
        :param cool_temperature: int
        :param holdtime: int
        :param zone_id: The index of the zone, defaults to 0.
        :return:
        """

        dt_holdtime = datetime.datetime.now() + datetime.timedelta(seconds=holdtime)

        holdtime = round(datetime.datetime.timestamp(dt_holdtime)*1e3)

        if heat_temperature is None and cool_temperature is None:
            # Just calling permanent hold on the current temperature
            heat_temperature = self.get_zone_heating_setpoint(zone_id)
            cool_temperature = self.get_zone_cooling_setpoint(zone_id)
        elif heat_temperature is not None and cool_temperature is not None:
            # Both heat and cool setpoints provided, continue
            pass
        else:
            # Not sure how I want to handle only one temperature provided, but this definitely assumes you're using
            # auto mode.
            raise AttributeError("Must either provide both heat and cool setpoints, or don't provide either")

        # Check that the setpoints are valid
        self.check_heat_cool_setpoints(heat_temperature, cool_temperature)

        # Set the thermostat
        url = self._get_zone_put_url("hold_time_and_setpoints", zone_id)
        data = {
            "hold_cooling_setpoint": cool_temperature,
            "hold_heating_setpoint": heat_temperature,
            'cooling_setpoint': cool_temperature,
            'cooling_integer': str(cool_temperature),
            'heating_setpoint': heat_temperature,
            'heating_integer': str(heat_temperature),
            "hold_time": holdtime,
            "permanent_hold": False
        }

        self._put_url(url, data)

    def set_zone_heat_cool_temp(self, heat_temperature=None, cool_temperature=None, set_temperature=None, zone_id=0):
        """
        Sets the heat and cool temperatures of the zone. You must provide either heat and cool temperatures, or just
        the set_temperature. This method will add deadband to the heat and cool temperature from the set temperature.

        :param heat_temperature: int or None
        :param cool_temperature: int or None
        :param set_temperature: int or None
        :param zone_id: The index of the zone, defaults to 0.
        :return: None
        """
        deadband = self.get_deadband()

        if set_temperature is None:
            if heat_temperature:
                heat_temperature = int(heat_temperature)
            else:
                heat_temperature = min(self.get_zone_heating_setpoint(zone_id), int(cool_temperature)-deadband)

            if cool_temperature:
                cool_temperature = int(cool_temperature)
            else:
                cool_temperature = max(self.get_zone_cooling_setpoint(zone_id), int(heat_temperature)+deadband)

        else:
            # This will smartly select either the ceiling of the floor temp depending on the current operating mode.
            zone_mode = self.get_zone_current_mode(zone_id)
            if zone_mode == self.OPERATION_MODE_COOL:
                cool_temperature = int(set_temperature)
                heat_temperature = min(self.get_zone_heating_setpoint(zone_id), int(cool_temperature)-deadband)
            elif zone_mode == self.OPERATION_MODE_HEAT:
                cool_temperature = max(self.get_zone_cooling_setpoint(zone_id), int(heat_temperature)+deadband)
                heat_temperature = int(set_temperature)
            else:
                cool_temperature = int(set_temperature) + math.ceil(deadband/2)
                heat_temperature = int(set_temperature) - math.ceil(deadband/2)

        zone_mode = self.get_zone_requested_mode(zone_id=zone_id)
        if zone_mode == self.OPERATION_MODE_AUTO:
            self.check_heat_cool_setpoints(heat_temperature, cool_temperature)
            url = self._get_zone_put_url("setpoints", zone_id)
            data = {
                'cooling_setpoint': cool_temperature,
                'cooling_integer': str(cool_temperature),
                'heating_setpoint': heat_temperature,
                'heating_integer': str(heat_temperature)
            }
            self._put_url(url, data)

        elif zone_mode == self.OPERATION_MODE_HEAT:
            self.check_heat_cool_setpoints(heat_temperature=heat_temperature)
            url = self._get_zone_put_url("setpoints", zone_id)
            data = {
                'heating_setpoint': heat_temperature,
                'heating_integer': str(heat_temperature)
            }
            self._put_url(url, data)

        elif zone_mode == self.OPERATION_MODE_COOL:
            self.check_heat_cool_setpoints(cool_temperature=cool_temperature)
            url = self._get_zone_put_url("setpoints", zone_id)
            data = {
                'cooling_setpoint': cool_temperature,
                'cooling_integer': str(cool_temperature),
            }
            self._put_url(url, data)

        else:
            # The system mode must be off
            pass

    def set_zone_preset(self, preset, zone_id=0):
        """
        Sets the preset of the specified zone.
        :param preset: str - The preset, see NexiaThermostat.get_zone_presets(zone_id)
        :param zone_id: The index of the zone, defaults to 0.
        :return: None
        """
        # Validate the data
        if preset in self.get_zone_presets(zone_id):
            if self.get_zone_preset(zone_id) != preset:
                url = self._get_zone_put_url("preset", zone_id)

                data = {
                    "preset_selected": preset
                }
                self._put_url(url, data)
        else:
            raise KeyError(f"Invalid preset \"{preset}\". Select one of the "
                           f"following: {self.get_zone_presets(zone_id)}")

    def set_zone_mode(self, mode, zone_id=0):
        """
        Sets the mode of the zone.
        :param mode: str - The mode, see NexiaThermostat.OPERATION_MODES
        :param zone_id: The index of the zone, defaults to 0.
        :return:
        """
        # Validate the data
        if mode in self.OPERATION_MODES:
            url = self._get_zone_put_url("zone_mode", zone_id)

            data = {"requested_zone_mode": mode}
            self._put_url(url, data)
        else:
            raise KeyError(f"Invalid mode \"{mode}\". Select one of the following: {self.OPERATION_MODES}")
