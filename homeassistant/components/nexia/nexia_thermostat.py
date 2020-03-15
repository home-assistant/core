""" Nexia Climate Device Access """

import datetime
import json
import math
import pprint
import time
from threading import Lock

import requests
from bs4 import BeautifulSoup

GLOBAL_LOGIN_ATTEMPTS = 4
GLOBAL_LOGIN_ATTEMPTS_LEFT = GLOBAL_LOGIN_ATTEMPTS


class NexiaThermostat:
    """ Nexia Climate Device Access Class """

    ROOT_URL = "https://www.mynexia.com"
    AUTH_FAILED_STRING = "https://www.mynexia.com/login"
    AUTH_FORGOTTEN_PASSWORD_STRING = (
        "https://www.mynexia.com/account/" "forgotten_credentials"
    )
    DEFAULT_UPDATE_RATE = 120  # 2 minutes
    DISABLE_AUTO_UPDATE = "Disable"
    PUT_UPDATE_DELAY = 0.5

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
    OPERATION_MODES = [
        OPERATION_MODE_AUTO,
        OPERATION_MODE_COOL,
        OPERATION_MODE_HEAT,
        OPERATION_MODE_OFF,
    ]

    # The order of these is important as it maps to preset#
    PRESET_MODE_HOME = "home"
    PRESET_MODE_AWAY = "away"
    PRESET_MODE_SLEEP = "sleep"
    PRESET_MODE_NONE = "none"
    PRESET_MODES = [
        PRESET_MODE_HOME,
        PRESET_MODE_AWAY,
        PRESET_MODE_SLEEP,
        PRESET_MODE_NONE,
    ]

    DAMPER_MODE_OPEN = "Damper Open"
    DAMPER_MODE_CLOSED = "Damper Closed"

    STATUS_COOL = "COOL"
    STATUS_HEAT = "HEAT"

    SYSTEM_STATUS_COOL = "Cooling"
    SYSTEM_STATUS_HEAT = "Heating"
    SYSTEM_STATUS_WAIT = "Waiting..."
    SYSTEM_STATUS_IDLE = "System Idle"

    AIR_CLEANER_MODE_AUTO = "auto"
    AIR_CLEANER_MODE_QUICK = "quick"
    AIR_CLEANER_MODE_ALLERGY = "allergy"
    AIR_CLEANER_MODES = [
        AIR_CLEANER_MODE_AUTO,
        AIR_CLEANER_MODE_QUICK,
        AIR_CLEANER_MODE_ALLERGY,
    ]

    HUMIDITY_MIN = 0.35
    HUMIDITY_MAX = 0.65

    UNIT_CELSIUS = "C"
    UNIT_FAHRENHEIT = "F"

    ALL_IDS = "all"

    def __init__(
        self,
        house_id: int,
        username=None,
        password=None,
        auto_login=True,
        update_rate=None,
    ):
        """
        Connects to and provides the ability to get and set parameters of your
        Nexia connected thermostat.

        :param house_id: int - Your house_id. You can get this from logging in
        and looking at the url once you're looking at your climate device.
        https://www.mynexia.com/houses/<house_id>/climate
        :param username: str - Your login email address
        :param password: str - Your login password
        :param auto_login: bool - Default is True, Login now (True), or login
        manually later (False)
        :param update_rate: int - How many seconds between requesting a new
        JSON update. Default is 300s.
        """

        self.username = username
        self.password = password
        self.house_id = house_id
        self.last_csrf = None
        self.thermostat_json = None
        self.last_update = None
        self.mutex = Lock()

        # Control the update rate
        if update_rate is None:
            self.update_rate = datetime.timedelta(seconds=self.DEFAULT_UPDATE_RATE)
        elif update_rate == self.DISABLE_AUTO_UPDATE:
            self.update_rate = self.DISABLE_AUTO_UPDATE
        else:
            self.update_rate = datetime.timedelta(seconds=update_rate)

        # Create a session
        self.session = requests.session()
        self.session.max_redirects = 3

        # Login if requested
        if auto_login:
            self.login()
            self.update()

    def _get_authenticity_token(self, url: str):
        """
        Returns the csrf param and token.
        :param url: str
        :return: dict with "token" and "param" keys
        """
        request = self._get_url(url)
        self._check_response("Failed to get authenticity token", request)
        soup = BeautifulSoup(request.text, "html5lib")
        param = soup.find("meta", attrs={"name": "csrf-param"})
        token = soup.find("meta", attrs={"name": "csrf-token"})
        if token and param:
            return {"token": token["content"], "param": param["content"]}

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

        headers = {"X-CSRF-Token": self.last_csrf, "X-Requested-With": "XMLHttpRequest"}
        # Let the code throw the exception
        # try:
        #     r = self.session.put(request_url, payload, headers=headers,
        #     allow_redirects=False)
        # except requests.RequestException as e:
        #     print("Error putting url", str(e))
        #     return None
        request = self.session.put(
            request_url, payload, headers=headers, allow_redirects=False
        )

        if request.status_code == 302:
            # assuming its redirecting to login
            self.login()
            request = self._put_url(url, payload)

        self._check_response(
            f"Failed PUT Request:\n" + f"  Url: {url}\n" + f"  Payload {str(payload)}",
            request,
        )

        # Assume something change, so update the thermostat's JSON
        time.sleep(self.PUT_UPDATE_DELAY)
        self.update()

        return request

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
        request = self.session.post(request_url, payload)

        if request.status_code == 302:
            # assuming its redirecting to login
            self.login()
            return self._post_url(url, payload)

        # Assume something changed, so update the thermostat's JSON
        time.sleep(self.PUT_UPDATE_DELAY)
        self.update()

        self._check_response("Failed to POST url", request)
        return request

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
        request = self.session.get(request_url, allow_redirects=False)

        if request.status_code == 302:
            # assuming its redirecting to login
            self.login()
            return self._get_url(url)

        self._check_response("Failed to GET url", request)
        return request

    @staticmethod
    def _check_response(error_text, request):
        """
        Checks the request response, throws exception with the description text
        :param error_text: str
        :param request: response
        :return: None
        """
        if request is None or request.status_code != 200:
            if request is not None:
                response = ""
                for key in request.__attrs__:
                    response += f"  {key}: {getattr(request, key)}\n"
                raise Exception(f"{error_text}\n{response}")
            raise Exception(f"No response from session. {error_text}")

    def _needs_update(self):
        """
        Returns True if an update is needed
        :return: bool
        """
        if self.update_rate == self.DISABLE_AUTO_UPDATE:
            return False
        if self.last_update is None:
            return True
        return datetime.datetime.now() - self.last_update > self.update_rate

    def _get_thermostat_json(self, thermostat_id=None, force_update=False):
        """
        Returns the thermostat's JSON data. It's either cached, or returned
        directly from the internet
        :param force_update: bool - Forces an update
        :return: dict(thermostat_jason)
        """
        with self.mutex:
            if (
                self.thermostat_json is None
                or self._needs_update()
                or force_update is True
            ):
                request = self._get_url(
                    "/houses/" + str(self.house_id) + "/xxl_thermostats"
                )
                if request and request.status_code == 200:
                    ts_json = json.loads(request.text)
                    if ts_json:
                        self.thermostat_json = ts_json
                        self.last_update = datetime.datetime.now()
                    else:
                        raise Exception("Nothing in the JSON")
                else:
                    self._check_response(
                        "Failed to get thermostat JSON, session probably timed" " out",
                        request,
                    )

        if thermostat_id == self.ALL_IDS:
            return self.thermostat_json
        if thermostat_id is not None:
            thermostat_json_dict = dict()
            for thermostat in self.thermostat_json:
                thermostat_json_dict.update({thermostat["id"]: thermostat})

            if thermostat_id in thermostat_json_dict:
                return thermostat_json_dict[thermostat_id]
            raise KeyError(
                f"Thermostat ID {thermostat_id} does not exist. Available IDs:"
                f" {thermostat_json_dict.keys()}"
            )
        if len(self.thermostat_json) == 1:
            return self.thermostat_json[0]

        raise IndexError(
            "More than one thermostat detected. You must provide a " "thermostat_id"
        )

    def _get_thermostat_key(self, key, thermostat_id=None):
        """
        Returns the thermostat value from the provided key in the thermostat's
        JSON.
        :param thermostat_id: int - the ID of the thermostat to use
        :param key: str
        :return: value
        """
        thermostat = self._get_thermostat_json(thermostat_id)
        if thermostat and key in thermostat:
            return thermostat[key]
        raise KeyError(f'Key "{key}" not in the thermostat JSON!')

    def _get_thermostat_put_url(self, text=None, thermostat_id=None):
        """
        Returns the PUT url from the text parameter
        :param thermostat_id: int - the ID of the thermostat to use
        :param text: str
        :return: str
        """
        if thermostat_id is None and len(self.get_thermostat_ids()) == 1:
            thermostat_id = self.get_thermostat_device_id()
        elif thermostat_id is None and len(self.get_thermostat_ids()) > 1:
            raise IndexError(
                "More than one thermostat detected. You must provide a " "thermostat_id"
            )
        elif thermostat_id and thermostat_id not in self.get_thermostat_ids():
            raise KeyError(
                f"Thermostat ID {thermostat_id} does not exist. Available IDs:"
                f" {self.get_thermostat_ids()}"
            )
        return (
            f"/houses/{str(self.house_id)}/xxl_thermostats/"
            f"{str(thermostat_id)}/{text if text else ''}"
        )

    def _get_zone_json(self, thermostat_id=None, zone_id=0):
        """
        Returns the thermostat zone's JSON
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: dict(thermostat_json['zones'][zone_id])
        """
        thermostat = self._get_thermostat_json(thermostat_id)
        if not thermostat:
            return None

        if len(thermostat["zones"]) > zone_id:
            return thermostat["zones"][zone_id]

        raise IndexError(
            f"The zone_id ({zone_id}) does not exist in the thermostat zones."
        )

    def _get_zone_key(self, key, thermostat_id=None, zone_id=0):
        """
        Returns the zone value for the key and zone_id provided.
        :param key: str
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: The value of the key/value pair.
        """
        zone = self._get_zone_json(thermostat_id, zone_id)
        if key in zone:
            return zone[key]

        raise KeyError(f'Zone {zone_id} key "{key}" invalid.')

    def _get_zone_put_url(self, text=None, thermostat_id=None, zone_id=0):
        """
        Returns the PUT url from the text parameter for a specific zone
        :param text: str
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.

        :return: str
        """
        zone_id = self._get_zone_key("id", thermostat_id, zone_id)
        return (
            "/houses/"
            + str(self.house_id)
            + "/xxl_zones/"
            + str(zone_id)
            + ("/" + text if text else "")
        )

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
        global GLOBAL_LOGIN_ATTEMPTS, GLOBAL_LOGIN_ATTEMPTS_LEFT
        if GLOBAL_LOGIN_ATTEMPTS_LEFT > 0:
            token = self._get_authenticity_token("/login")
            if token:
                payload = {
                    "login": self.username,
                    "password": self.password,
                    token["param"]: token["token"],
                }
                self.last_csrf = token["token"]

                request = self._post_url("/session", payload)

                if (
                    request is None
                    or request.status_code != 200
                    and request.status_code != 302
                ):
                    GLOBAL_LOGIN_ATTEMPTS_LEFT -= 1
                self._check_response("Failed to login", request)

                if request.url == self.AUTH_FORGOTTEN_PASSWORD_STRING:
                    raise Exception(
                        f"Failed to login, getting redirected to {request.url}"
                        f". Try to login manually on the website."
                    )

            else:
                raise Exception("Failed to get csrf token")
        else:
            raise Exception(
                f"Failed to login after {GLOBAL_LOGIN_ATTEMPTS} attempts! Any "
                f"more attempts may lock your account!"
            )

    def get_last_update(self):
        """
        Returns a string indicating the ISO formatted time string of the last
        update
        :return: The ISO formatted time string of the last update,
        datetime.datetime.min if never updated
        """
        if self.last_update is None:
            return datetime.datetime.isoformat(datetime.datetime.min)
        return datetime.datetime.isoformat(self.last_update)

    def update(self):
        """
        Forces a status update
        :return: None
        """
        self._get_thermostat_json(thermostat_id=self.ALL_IDS, force_update=True)

    ########################################################################
    # Print Functions

    def print_thermostat_data(self, thermostat_id=None):
        """
        Prints just the thermostat data, no zone data
        :param thermostat_id: int - the ID of the thermostat to use
        :return: None
        """
        thermostat_json = self._get_thermostat_json(thermostat_id).copy()
        thermostat_json.pop("zones")
        pprint.pprint(thermostat_json)

    def print_zone_data(self, thermostat_id=None, zone_id=None):
        """
        Prints the specified zone data
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: None
        """
        thermostat_json = self._get_zone_json(thermostat_id, zone_id)
        pprint.pprint(thermostat_json)

    def print_all_json_data(self):
        """
        Prints all thermostat data
        :return: None
        """
        thermostat_json = self._get_thermostat_json(self.ALL_IDS)
        pprint.pprint(thermostat_json)

    ########################################################################
    # Thermostat Attributes

    def get_thermostat_ids(self):
        """
        Returns the number of thermostats available to Nexia
        :return:
        """
        ids = list()
        for thermostat in self._get_thermostat_json(thermostat_id=self.ALL_IDS):
            ids.append(thermostat["id"])
        return ids

    def get_thermostat_model(self, thermostat_id=None):
        """
        Returns the thermostat model
        :param thermostat_id: int - the ID of the thermostat to use
        :return: string
        """
        return self._get_thermostat_key("model_number", thermostat_id)

    def get_thermostat_firmware(self, thermostat_id=None):
        """
        Returns the thermostat firmware version
        :param thermostat_id: int - the ID of the thermostat to use
        :return: string
        """
        return self._get_thermostat_key("firmware_build_name", thermostat_id)

    def get_thermostat_dev_build_number(self, thermostat_id=None):
        """
        Returns the thermostat development build number.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: string
        """
        return self._get_thermostat_key("dev_build_number", thermostat_id)

    def get_thermostat_device_id(self, thermostat_id=None):
        """
        Returns the device id
        :param thermostat_id: int - the ID of the thermostat to use
        :return: string
        """
        return self._get_thermostat_key("id", thermostat_id)

    def get_thermostat_house_id(self, thermostat_id=None):
        """
        Returns the thermostat house id
        :param thermostat_id: int - the ID of the thermostat to use
        :return: str
        """
        return self._get_thermostat_key("house_id", thermostat_id)

    def get_thermostat_dealer_id(self, thermostat_id=None):
        """
        Returns the thermostat dealer id (phone number)
        :param thermostat_id: int - the ID of the thermostat to use
        :return: str
        """
        return self._get_thermostat_key("dealer_identifier", thermostat_id)

    def get_thermostat_type(self, thermostat_id=None):
        """
        Returns the thermostat type, such as TraneXl1050
        :param thermostat_id: int - the ID of the thermostat to use
        :return: str
        """
        return self._get_thermostat_key("type", thermostat_id)

    def get_thermostat_name(self, thermostat_id=None):
        """
        Returns the name of the thermostat. This is not the zone name.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: str
        """
        return self._get_thermostat_key("name", thermostat_id)

    ########################################################################
    # Supported Features

    def has_outdoor_temperature(self, thermostat_id=None):
        """
        Capability indication of whether the thermostat has an outdoor
        temperature sensor
        :param thermostat_id: int - the ID of the thermostat to use
        :return: bool
        """
        return self._get_thermostat_key("have_odt", thermostat_id)

    def has_relative_humidity(self, thermostat_id=None):
        """
        Capability indication of whether the thermostat has an relative
        humidity sensor
        :param thermostat_id: int - the ID of the thermostat to use
        :return: bool
        """
        return self._get_thermostat_key("have_rh", thermostat_id)

    def has_variable_speed_compressor(self, thermostat_id=None):
        """
        Capability indication of whether the thermostat has a variable speed
        compressor
        :param thermostat_id: int - the ID of the thermostat to use
        :return: bool
        """
        return self._get_thermostat_key("has_variable_speed_compressor", thermostat_id)

    def has_emergency_heat(self, thermostat_id=None):
        """
        Capability indication of whether the thermostat has emergency/aux heat.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: bool
        """
        return self._get_thermostat_key("emergency_heat_supported", thermostat_id)

    def has_variable_fan_speed(self, thermostat_id=None):
        """
        Capability indication of whether the thermostat has a variable speed
        blower
        :param thermostat_id: int - the ID of the thermostat to use
        :return: bool
        """
        return self._get_thermostat_key("fan_type", thermostat_id) == "VSPD"

    ########################################################################
    # System Attributes

    def get_deadband(self, thermostat_id=None):
        """
        Returns the deadband of the thermostat. This is the minimum number of
        degrees between the heat and cool setpoints in the number of degrees in
        the temperature unit selected by the
        thermostat.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: int
        """
        return self._get_thermostat_key("temperature_deadband", thermostat_id)

    def get_setpoint_limits(self, thermostat_id=None):
        """
        Returns a tuple of the minimum and maximum temperature that can be set
        on any zone. This is in the temperature unit selected by the
        thermostat.
        :return: (int, int)
        """
        return (
            self._get_thermostat_key("temperature_low_limit", thermostat_id),
            self._get_thermostat_key("temperature_high_limit", thermostat_id),
        )

    def get_variable_fan_speed_limits(self, thermostat_id=None):
        """
        Returns the variable fan speed setpoint limits of the thermostat.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: (float, float)
        """
        if self.has_variable_fan_speed(thermostat_id):
            return (
                self._get_thermostat_key("min_fan_speed", thermostat_id),
                self._get_thermostat_key("max_fan_speed", thermostat_id),
            )
        raise AttributeError("This thermostat does not support fan speeds")

    def get_unit(self, thermostat_id=None):
        """
        Returns the temperature unit used by this system, either C or F.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: str
        """
        return self._get_thermostat_key("scale", thermostat_id).upper()

    def get_humidity_setpoint_limits(self, thermostat_id=None):
        """
        Returns the humidity setpoint limits of the thermostat.

        This is a hard-set limit in this code that I believe is universal to
        all TraneXl thermostats.
        :param thermostat_id: int - the ID of the thermostat to use (unused,
        but kept for consistency)
        :return: (float, float)
        """
        return self.HUMIDITY_MIN, self.HUMIDITY_MAX

    ########################################################################
    # System Universal Boolean Get Methods

    def is_blower_active(self, thermostat_id=None):
        """
        Returns True if the blower is active
        :param thermostat_id: int - the ID of the thermostat to use
        :return: bool
        """
        return self._get_thermostat_key("blower_active", thermostat_id)

    def is_emergency_heat_active(self, thermostat_id=None):
        """
        Returns True if the emergency/aux heat is active
        :param thermostat_id: int - the ID of the thermostat to use
        :return: bool
        """
        if self.has_emergency_heat():
            return self._get_thermostat_key("emergency_heat_active", thermostat_id)
        raise Exception("This system does not support emergency heat")

    ########################################################################
    # System Universal Get Methods

    def get_fan_mode(self, thermostat_id=None):
        """
        Returns the current fan mode. See FAN_MODES for the available options.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: str
        """
        return self._get_thermostat_key("fan_mode", thermostat_id)

    def get_outdoor_temperature(self, thermostat_id=None):
        """
        Returns the outdoor temperature.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: float
        """
        if self.has_outdoor_temperature(thermostat_id):
            return float(self._get_thermostat_key("outdoor_temperature", thermostat_id))
        raise Exception("This system does not have an outdoor temperature sensor")

    def get_relative_humidity(self, thermostat_id=None):
        """
        Returns the indoor relative humidity as a percent (0-1)
        :param thermostat_id: int - the ID of the thermostat to use
        :return: float
        """
        if self.has_relative_humidity(thermostat_id):
            return self._get_thermostat_key("current_relative_humidity", thermostat_id)
        raise Exception("This system does not have a relative humidity sensor.")

    def get_current_compressor_speed(self, thermostat_id=None):
        """
        Returns the variable compressor speed, if supported, as a percent (0-1)
        :param thermostat_id: int - the ID of the thermostat to use
        :return: float
        """
        if self.has_variable_speed_compressor(thermostat_id):
            return self._get_thermostat_key("compressor_speed", thermostat_id)
        raise Exception(
            "This system does not have a variable speed compressor.", thermostat_id
        )

    def get_requested_compressor_speed(self, thermostat_id=None):
        """
        Returns the variable compressor's requested speed, if supported, as a
        percent (0-1)
        :param thermostat_id: int - the ID of the thermostat to use
        :return: float
        """
        if self.has_variable_speed_compressor(thermostat_id):
            return self._get_thermostat_key("requested_compressor_speed", thermostat_id)
        raise Exception("This system does not have a variable speed compressor.")

    def get_fan_speed_setpoint(self, thermostat_id=None):
        """
        Returns the current variable fan speed setpoint from 0-1.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: float
        """
        if self.has_variable_fan_speed(thermostat_id):
            return self._get_thermostat_key("fan_speed", thermostat_id)
        raise AttributeError("This system does not have variable fan speed.")

    def get_dehumidify_setpoint(self, thermostat_id=None):
        """
        Returns the dehumidify setpoint from 0-1
        :param thermostat_id: int - the ID of the thermostat to use
        :return: float
        """
        return self._get_thermostat_key("dehumidify_setpoint", thermostat_id)

    def get_system_status(self, thermostat_id=None):
        """
        Returns the system status such as "System Idle" or "Cooling"
        :param thermostat_id: int - the ID of the thermostat to use
        :return: str
        """
        return self._get_thermostat_key("system_status", thermostat_id)

    def get_air_cleaner_mode(self, thermostat_id=None):
        """
        Returns the system's air cleaner mode
        :param thermostat_id: int - the ID of the thermostat to use
        :return: str
        """
        return self._get_thermostat_key("air_cleaner_mode", thermostat_id)

    ########################################################################
    # System Universal Set Methods

    def set_fan_mode(self, fan_mode: str, thermostat_id=None):
        """
        Sets the fan mode.
        :param fan_mode: string that must be in NexiaThermostat.FAN_MODES
        :param thermostat_id: int - the ID of the thermostat to use
        :return: None
        """
        fan_mode = fan_mode.lower()
        if fan_mode in self.FAN_MODES:
            url = self._get_thermostat_put_url("fan_mode", thermostat_id)
            data = {"fan_mode": fan_mode}
            self._put_url(url, data)
        else:
            raise KeyError("Invalid fan mode specified")

    # TODO: Figure out what the PUT url is... I can't seem to set the fan speed
    #  from the website, but the capability exists in the Nexia app for iOS.
    # def set_fan_setpoint(self, fan_setpoint: float):
    #     """
    #     Sets the fan's setpoint speed as a percent in range. You can see the
    #     limits by calling Nexia.get_variable_fan_speed_limits()
    #     :param fan_setpoint: float
    #     :return: None
    #     """
    #
    #     # This call will get the limits, as well as check if this system has
    #     # a variable speed fan
    #     min_speed, max_speed = self.get_variable_fan_speed_limits()
    #
    #     if min_speed <= fan_setpoint <= max_speed:
    #         url = self._get_thermostat_put_url("?????")
    #         data = {"fan_mode": self.get_fan_mode(),
    #                 "fan_speed": fan_setpoint}
    #         self._put_url(url, data)
    #     else:
    #         raise ValueError(f"The fan setpoint, {fan_setpoint} is not "
    #         f"between {min_speed} and {max_speed}.")

    def set_air_cleaner(self, air_cleaner_mode: str, thermostat_id):
        """
        Sets the air cleaner mode.
        :param air_cleaner_mode: string that must be in
        NexiaThermostat.AIR_CLEANER_MODES
        :param thermostat_id: int - the ID of the thermostat to use
        :return: None
        """
        air_cleaner_mode = air_cleaner_mode.lower()
        if air_cleaner_mode in self.AIR_CLEANER_MODES:
            if air_cleaner_mode != self.get_air_cleaner_mode(thermostat_id):
                url = self._get_thermostat_put_url("air_cleaner_mode", thermostat_id)
                data = {"air_cleaner_mode": air_cleaner_mode}
                self._put_url(url, data)
        else:
            raise KeyError("Invalid air cleaner mode specified")

    def set_follow_schedule(self, follow_schedule, thermostat_id):
        """
        Enables or disables scheduled operation
        :param follow_schedule: bool - True for follow schedule, False for hold
        current setpoints
        :param thermostat_id: int - the ID of the thermostat to use
        :return: None
        """
        url = self._get_thermostat_put_url("scheduling_enabled", thermostat_id)
        data = {"scheduling_enabled": "enabled" if follow_schedule else "disabled"}
        self._put_url(url, data)

    def set_emergency_heat(self, emergency_heat_on, thermostat_id):
        """
        Enables or disables emergency / auxillary heat.
        :param emergency_heat_on: bool - True for enabled, False for Disabled
        :param thermostat_id: int - the ID of the thermostat to use
        :return: None
        """
        if self.has_emergency_heat(thermostat_id):
            url = self._get_thermostat_put_url("emergency_heat", thermostat_id)
            data = {"emergency_heat_active": bool(emergency_heat_on)}
            self._put_url(url, data)
        else:
            raise Exception("This thermostat does not support emergency heat.")

    def set_dehumidify_setpoint(self, dehumidify_setpoint, thermostat_id):
        """
        Sets the overall system's dehumidify setpoint as a percent (0-1).

        The system must support
        :param dehumidify_setpoint: float
        :param thermostat_id: int - the ID of the thermostat to use
        :return: None
        """
        if self.has_relative_humidity(thermostat_id):
            (min_humidity, max_humidity) = self.get_humidity_setpoint_limits(
                thermostat_id
            )

            if min_humidity <= dehumidify_setpoint <= max_humidity:
                url = self._get_thermostat_put_url("humidity_setpoints", thermostat_id)
                data = {
                    "dehumidify_setpoint": dehumidify_setpoint,
                    "dehumidify_allowed": True,
                    "id": self.get_thermostat_device_id(),
                    "humidify_setpoint": 0.50,
                    "humidify_allowed": False,
                }
                self._put_url(url, data)
            else:
                raise ValueError(
                    f"humidity_level out of range ({min_humidity} - " f"{max_humidity})"
                )
        else:
            raise Exception(
                "Setting target humidity is not supported on this thermostat."
            )

    # TODO - Do any system's actually support humidifying? I.e. putting
    #  moisture into a controlled space?

    ########################################################################
    # Zone Get Methods

    def get_zone_ids(self, thermostat_id=None):
        """
        Returns a list of available zone IDs with a starting index of 0.
        :param thermostat_id: int - the ID of the thermostat to use
        :return: list(int)
        """
        # The zones are in a list, so there are no keys to pull out. I have to
        # create a new list of IDs.
        return list(range(len(self._get_thermostat_key("zones", thermostat_id))))

    def get_zone_name(self, thermostat_id=None, zone_id=0):
        """
        Returns the zone name
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return str(
            self._get_zone_key("name", thermostat_id=thermostat_id, zone_id=zone_id)
        )

    def get_zone_cooling_setpoint(self, thermostat_id=None, zone_id=0):
        """
        Returns the cooling setpoint in the temperature unit of the thermostat
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: int
        """
        return self._get_zone_key(
            "cooling_setpoint", thermostat_id=thermostat_id, zone_id=zone_id
        )

    def get_zone_heating_setpoint(self, thermostat_id=None, zone_id=0):
        """
        Returns the heating setpoint in the temperature unit of the thermostat
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: int
        """
        return self._get_zone_key(
            "heating_setpoint", thermostat_id=thermostat_id, zone_id=zone_id
        )

    def get_zone_current_mode(self, thermostat_id=None, zone_id=0):
        """
        Returns the current mode of the zone. This may not match the requested
        mode
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return str(
            self._get_zone_key(
                "last_zone_mode", thermostat_id=thermostat_id, zone_id=zone_id
            ).upper()
        )

    def get_zone_requested_mode(self, thermostat_id=None, zone_id=0):
        """
        Returns the requested mode of the zone. This should match the zone's
        mode on the thermostat.
        Available options can be found in NexiaThermostat.OPERATION_MODES
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return self._get_zone_key(
            "requested_zone_mode", thermostat_id=thermostat_id, zone_id=zone_id
        ).upper()

    def get_zone_temperature(self, thermostat_id=None, zone_id=0):
        """
        Returns the temperature of the zone in the temperature unit of the
        thermostat.
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: int
        """
        return self._get_zone_key(
            "temperature", thermostat_id=thermostat_id, zone_id=zone_id
        )

    def get_zone_presets(self, thermostat_id=None, zone_id=0):
        """
        Supposed to return the zone presets. For some reason, most of the time,
        my unit only returns "AWAY", but I can set the other modes. There is
        the capability to add additional zone presets on the main thermostat,
        so this may not work as expected.

        TODO: Try to get this working more reliably
        :param thermostat_id: int - Doesn't do anythign as of the current
        implementation
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: int - Doesn't do anything as of the current
        implementation
        :return:
        """
        # return self._get_zone_key("presets", zone_id=zone_id)
        # Can't get Nexia to return all of the presets occasionally, but I
        # don't think there would be any other "presets" available anyway...
        return self.PRESET_MODES

    def get_zone_preset(self, thermostat_id=None, zone_id=0):
        """
        Returns the zone's currently selected preset. Should be one of the
        strings in NexiaThermostat.get_zone_presets(zone_id).
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return self._get_zone_key(
            "preset_selected", thermostat_id=thermostat_id, zone_id=zone_id
        )

    def get_zone_preset_setpoints(self, preset, thermostat_id=None, zone_id=0):
        """
        Returns the setpoints of the provided preset in the zone provided.
        :param preset: str - The preset to get the setpoints from
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: (int, int)
        """
        if preset != self.PRESET_MODE_NONE:
            index = (
                self.get_zone_presets(
                    thermostat_id=thermostat_id, zone_id=zone_id
                ).index(preset)
                + 1
            )
            return (
                self._get_zone_key(
                    f"preset_cool{index}", thermostat_id=thermostat_id, zone_id=zone_id
                ),
                self._get_zone_key(
                    f"preset_heat{index}", thermostat_id=thermostat_id, zone_id=zone_id
                ),
            )
        raise KeyError(
            f"'{self.PRESET_MODE_NONE}'' preset mode does not have any preset"
            f" values."
        )

    def get_zone_status(self, thermostat_id=None, zone_id=0):
        """
        Returns the zone status.
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return self._get_zone_key(
            "zone_status", thermostat_id=thermostat_id, zone_id=zone_id
        )

    def get_zone_setpoint_status(self, thermostat_id=None, zone_id=0):
        """
        Returns the setpoint status, like "Following Schedule - Home", or
        "Holding Permanently"
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: str
        """
        return self._get_zone_key(
            "setpoint_status", thermostat_id=thermostat_id, zone_id=zone_id
        )

    def is_zone_calling(self, thermostat_id=None, zone_id=0):
        """
        Returns True if the zone is calling for heat/cool.
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: bool
        """
        return (
            self._get_zone_key(
                "on_off_code", thermostat_id=thermostat_id, zone_id=zone_id
            )
            == "CALL"
        )

    def check_heat_cool_setpoints(
        self, heat_temperature=None, cool_temperature=None, thermostat_id=None
    ):
        """
        Checks the heat and cool setpoints to check if they are within the
        appropriate range and within the deadband limits.

        Will throw exception if not valid.
        :param heat_temperature: int
        :param cool_temperature: int
        :param thermostat_id: int - the ID of the thermostat to use
        :return: None
        """

        deadband = self.get_deadband(thermostat_id)
        (min_temperature, max_temperature) = self.get_setpoint_limits(thermostat_id)

        if heat_temperature is not None:
            heat_temperature = self.round_temp(heat_temperature, thermostat_id)
        if cool_temperature is not None:
            cool_temperature = self.round_temp(cool_temperature, thermostat_id)

        if (
            heat_temperature is not None
            and cool_temperature is not None
            and not heat_temperature < cool_temperature
        ):
            raise AttributeError(
                f"The heat setpoint ({heat_temperature}) must be less than the"
                f" cool setpoint ({cool_temperature})."
            )
        if (
            heat_temperature is not None
            and cool_temperature is not None
            and not cool_temperature - heat_temperature >= deadband
        ):
            raise AttributeError(
                f"The heat and cool setpoints must be at least {deadband} "
                f"degrees different."
            )
        if heat_temperature is not None and not heat_temperature <= max_temperature:
            raise AttributeError(
                f"The heat setpoint ({heat_temperature} must be less than the "
                f"maximum temperature of {max_temperature} degrees."
            )
        if cool_temperature is not None and not cool_temperature >= min_temperature:
            raise AttributeError(
                f"The cool setpoint ({cool_temperature}) must be greater than "
                f"the minimum temperature of {min_temperature} degrees."
            )
        # The heat and cool setpoints appear to be valid.

    ########################################################################
    # Zone Set Methods

    def call_return_to_schedule(self, thermostat_id=None, zone_id=0):
        """
        Tells the zone to return to its schedule.
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: None
        """

        # Set the thermostat
        url = self._get_zone_put_url(
            "return_to_schedule", thermostat_id=thermostat_id, zone_id=zone_id
        )
        data = {}
        self._put_url(url, data)

    def call_permanent_hold(
        self,
        heat_temperature=None,
        cool_temperature=None,
        thermostat_id=None,
        zone_id=0,
    ):
        """
        Tells the zone to call a permanent hold. Optionally can provide the
        temperatures.
        :param heat_temperature:
        :param cool_temperature:
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return:
        """

        if heat_temperature is None and cool_temperature is None:
            # Just calling permanent hold on the current temperature
            heat_temperature = self.get_zone_heating_setpoint(
                thermostat_id=thermostat_id, zone_id=zone_id
            )
            cool_temperature = self.get_zone_cooling_setpoint(
                thermostat_id=thermostat_id, zone_id=zone_id
            )
        elif heat_temperature is not None and cool_temperature is not None:
            # Both heat and cool setpoints provided, continue
            pass
        else:
            # Not sure how I want to handle only one temperature provided, but
            # this definitely assumes you're using auto mode.
            raise AttributeError(
                "Must either provide both heat and cool setpoints, or don't "
                "provide either"
            )

        # Check that the setpoints are valid
        self.check_heat_cool_setpoints(
            heat_temperature, cool_temperature, thermostat_id=thermostat_id
        )

        # Set the thermostat
        url = self._get_zone_put_url(
            "permanent_hold", thermostat_id=thermostat_id, zone_id=zone_id
        )
        data = {
            "hold_cooling_setpoint": cool_temperature,
            "hold_heating_setpoint": heat_temperature,
            "cooling_setpoint": cool_temperature,
            "cooling_integer": str(cool_temperature),
            "heating_setpoint": heat_temperature,
            "heating_integer": str(heat_temperature),
            "hold_time": 0,
            "permanent_hold": True,
        }
        self._put_url(url, data)

    def call_temporary_hold(
        self,
        heat_temperature=None,
        cool_temperature=None,
        holdtime=0,
        thermostat_id=None,
        zone_id=0,
    ):
        """
        Call a temporary hold. If the holdtime is 0, it will simply hold until
        the next scheduled
        time.
        :param heat_temperature: int
        :param cool_temperature: int
        :param holdtime: int
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return:
        """

        dt_holdtime = datetime.datetime.now() + datetime.timedelta(seconds=holdtime)

        holdtime = round(datetime.datetime.timestamp(dt_holdtime) * 1e3)

        if heat_temperature is None and cool_temperature is None:
            # Just calling permanent hold on the current temperature
            heat_temperature = self.get_zone_heating_setpoint(
                thermostat_id=thermostat_id, zone_id=zone_id
            )
            cool_temperature = self.get_zone_cooling_setpoint(
                thermostat_id=thermostat_id, zone_id=zone_id
            )
        elif heat_temperature is not None and cool_temperature is not None:
            # Both heat and cool setpoints provided, continue
            pass
        else:
            # Not sure how I want to handle only one temperature provided, but
            # this definitely assumes you're using auto mode.
            raise AttributeError(
                "Must either provide both heat and cool setpoints, or don't"
                "provide either"
            )

        # Check that the setpoints are valid
        self.check_heat_cool_setpoints(
            heat_temperature, cool_temperature, thermostat_id=thermostat_id
        )

        # Set the thermostat
        url = self._get_zone_put_url(
            "hold_time_and_setpoints", thermostat_id=thermostat_id, zone_id=zone_id
        )
        data = {
            "hold_cooling_setpoint": cool_temperature,
            "hold_heating_setpoint": heat_temperature,
            "cooling_setpoint": cool_temperature,
            "cooling_integer": str(cool_temperature),
            "heating_setpoint": heat_temperature,
            "heating_integer": str(heat_temperature),
            "hold_time": holdtime,
            "permanent_hold": False,
        }

        self._put_url(url, data)

    def set_zone_heat_cool_temp(
        self,
        heat_temperature=None,
        cool_temperature=None,
        set_temperature=None,
        thermostat_id=None,
        zone_id=0,
    ):
        """
        Sets the heat and cool temperatures of the zone. You must provide
        either heat and cool temperatures, or just the set_temperature. This
        method will add deadband to the heat and cool temperature from the set
        temperature.

        :param heat_temperature: int or None
        :param cool_temperature: int or None
        :param set_temperature: int or None
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: None
        """
        deadband = self.get_deadband(thermostat_id)

        if set_temperature is None:
            if heat_temperature:
                heat_temperature = self.round_temp(heat_temperature, thermostat_id)
            else:
                heat_temperature = min(
                    self.get_zone_heating_setpoint(
                        thermostat_id=thermostat_id, zone_id=zone_id
                    ),
                    self.round_temp(cool_temperature, thermostat_id) - deadband,
                )

            if cool_temperature:
                cool_temperature = self.round_temp(cool_temperature, thermostat_id)
            else:
                cool_temperature = max(
                    self.get_zone_cooling_setpoint(
                        thermostat_id=thermostat_id, zone_id=zone_id
                    ),
                    self.round_temp(heat_temperature, thermostat_id) + deadband,
                )

        else:
            # This will smartly select either the ceiling of the floor temp
            # depending on the current operating mode.
            zone_mode = self.get_zone_current_mode(
                thermostat_id=thermostat_id, zone_id=zone_id
            )
            if zone_mode == self.OPERATION_MODE_COOL:
                cool_temperature = self.round_temp(set_temperature, thermostat_id)
                heat_temperature = min(
                    self.get_zone_heating_setpoint(
                        thermostat_id=thermostat_id, zone_id=zone_id
                    ),
                    self.round_temp(cool_temperature, thermostat_id) - deadband,
                )
            elif zone_mode == self.OPERATION_MODE_HEAT:
                cool_temperature = max(
                    self.get_zone_cooling_setpoint(
                        thermostat_id=thermostat_id, zone_id=zone_id
                    ),
                    self.round_temp(heat_temperature, thermostat_id) + deadband,
                )
                heat_temperature = self.round_temp(set_temperature, thermostat_id)
            else:
                cool_temperature = self.round_temp(
                    set_temperature, thermostat_id
                ) + math.ceil(deadband / 2)
                heat_temperature = self.round_temp(
                    set_temperature, thermostat_id
                ) - math.ceil(deadband / 2)

        self.check_heat_cool_setpoints(
            heat_temperature, cool_temperature, thermostat_id=thermostat_id
        )
        url = self._get_zone_put_url(
            "setpoints", thermostat_id=thermostat_id, zone_id=zone_id
        )
        data = {
            "cooling_setpoint": cool_temperature,
            "cooling_integer": str(cool_temperature),
            "heating_setpoint": heat_temperature,
            "heating_integer": str(heat_temperature),
        }
        self._put_url(url, data)

    def set_zone_preset(self, preset, thermostat_id=None, zone_id=0):
        """
        Sets the preset of the specified zone.
        :param preset: str - The preset, see
        NexiaThermostat.get_zone_presets(zone_id)
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return: None
        """
        # TODO: Fix validation once a better way to get presets is determined.
        # Validate the data
        # if preset in self.get_zone_presets(zone_id):
        #     if self.get_zone_preset(zone_id) != preset:
        #         url = self._get_zone_put_url("preset", zone_id)
        #
        #         data = {
        #             "preset_selected": preset
        #         }
        #         self._put_url(url, data)
        # else:
        #     raise KeyError(f"Invalid preset \"{preset}\". Select one of the "
        #                    f"following: {self.get_zone_presets(zone_id)}")
        if self.get_zone_preset(thermostat_id=thermostat_id, zone_id=zone_id) != preset:
            url = self._get_zone_put_url(
                "preset", thermostat_id=thermostat_id, zone_id=zone_id
            )

            data = {"preset_selected": preset}
            self._put_url(url, data)

    def set_zone_mode(self, mode, thermostat_id=None, zone_id=0):
        """
        Sets the mode of the zone.
        :param mode: str - The mode, see NexiaThermostat.OPERATION_MODES
        :param thermostat_id: int - the ID of the thermostat to use
        :param zone_id: The index of the zone, defaults to 0.
        :return:
        """
        # Validate the data
        if mode in self.OPERATION_MODES:
            url = self._get_zone_put_url(
                "zone_mode", thermostat_id=thermostat_id, zone_id=zone_id
            )

            data = {"requested_zone_mode": mode}
            self._put_url(url, data)
        else:
            raise KeyError(
                f'Invalid mode "{mode}". Select one of the following: '
                f"{self.OPERATION_MODES}"
            )

    def round_temp(self, temperature: float, thermostat_id=None):
        """
        Rounds the temperature to the nearest 1/2 degree for C and neareast 1
        degree for F
        :param temperature: temperature to round
        :param thermostat_id: int - the ID of the thermostat to use
        :return: float rounded temperature
        """
        if self.get_unit(thermostat_id) == self.UNIT_CELSIUS:
            temperature *= 2
            temperature = round(temperature)
            temperature /= 2
        else:
            temperature = round(temperature)
        return temperature
