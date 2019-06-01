import requests
from bs4 import BeautifulSoup

import time
import datetime
import json
import math

class NexiaThermostat:

    ROOT_URL = "https://www.mynexia.com"
    AUTH_FAILED_STRING = "https://www.mynexia.com/login"
    UPDATE_RATE = 300  # 5 minutes

    username = None
    password = None
    house_id = None

    session = None
    last_csrf = None

    thermostat_json = None

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


    def __init__(self, house_id, username=None, password=None, auto_login=True, update_rate=None):

        self.username = username
        self.password = password
        self.house_id = house_id

        # Control the update rate
        if update_rate is None:
            self.update_rate = datetime.timedelta(seconds=self.UPDATE_RATE)
        else:
            self.update_rate = datetime.timedelta(seconds=update_rate)

        self.last_update = None

        self.session = requests.session()
        self.session.max_redirects = 3
        
        if auto_login:
            self.login()

    def login(self):
        print("Logging in as " + self.username)
        token = self._get_authenticity_token("/login")
        if token:
            payload = {
                'login': self.username,
                'password': self.password,
                token['param']: token['token']
            }
            self.last_csrf = token['token']
            print("posting login")
            r = self._post_url("/session", payload)
            self._check_response("Failed to login", r)
        else:
            raise Exception("Failed to get csrf token")

    def _get_authenticity_token(self, url):
        print("getting auth token")
        r = self._get_url(url)
        self._check_response("Failed to get authenticity token", r)
        print("parsing csrf token")
        soup = BeautifulSoup(r.text, 'html5lib')
        param = soup.find("meta", attrs={'name': "csrf-param"})
        token = soup.find("meta", attrs={'name': "csrf-token"})
        if token and param:
            return {
                "token": token['content'],
                "param": param['content']
            }

    def _put_url(self, url, payload):
        request_url = self.ROOT_URL + url

        # Debug
        print("Url:", str(url), "\nPayload:", str(payload))

        if not self.last_csrf:
            self.login()

        headers = {
            "X-CSRF-Token": self.last_csrf,
            "X-Requested-With": "XMLHttpRequest"
        }
        try:
            r = self.session.put(request_url, payload, headers=headers, allow_redirects=False)
        except requests.RequestException as e:
            print("Error putting url", str(e))
            return None
        if r.status_code == 302:
            # assuming its redirecting to login
            self.login()
            r = self._put_url(url, payload)

        self._check_response("Failed PUT Request", r)
        self.update()
        return r

    def _post_url(self, url, payload):
        request_url = self.ROOT_URL + url
        try:
            r = self.session.post(request_url, payload)
        except requests.RequestException as e:
            print("Error posting url", str(e))
            return None

        if r.status_code == 302:
            # assuming its redirecting to login
            self.login()
            return self._post_url(url, payload)

        self._check_response("Failed to POST url", r)
        return r

    def _get_url(self, url):
        request_url = self.ROOT_URL + url

        try:
            r = self.session.get(request_url, allow_redirects=False)
        except requests.RequestException as e:
            print("Error getting url", str(e))
            return None

        if r.status_code == 302:
            # assuming its redirecting to login
            self.login()
            return self._get_url(url)

        self._check_response("Failed to GET url", r)
        return r

    def _get_zone_key(self, key, zone_id=0):
        zone = self._get_zone(zone_id)
        if not zone:
            raise KeyError("Zone {0} invalid.".format(zone_id))

        if key in zone:
            return zone[key]
        raise KeyError("Zone {0} key \"{1}\" invalid.".format(zone_id, key))

    def _get_thermostat_key(self, key):
        thermostat = self._get_thermostat_json()
        if thermostat and key in thermostat:
            return thermostat[key]
        raise KeyError("Key \"{0}\" not in the thermostat JSON!".format(key))

    def _get_zone(self, zone_id=0):
        thermostat = self._get_thermostat_json()
        if not thermostat:
            return None
        if len(thermostat['zones']) > zone_id:
            return thermostat['zones'][zone_id]
        return None

    def _get_thermostat_json(self):
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

    def _check_response(self, description, r):
        if r is None or r.status_code != 200:
            response = ""
            for key in r.__attrs__:
                response += "  {key}: {value}\n".format(key=key, value=getattr(r, key))
            raise Exception("{description}: \n{response}".format(description=description, response=response))


    def _needs_update(self):
        if self.last_update is None:
            return True
        else:
            return datetime.datetime.now() - self.last_update > self.update_rate

    def get_last_update(self):
        if self.last_update is None:
            return "Never"
        else:
            return datetime.datetime.isoformat(self.last_update)

    def update(self):
        self.thermostat_json = None
        self._get_thermostat_json()

    def print_all_zone_data(self, zone_id):
        json = self._get_zone(zone_id)
        for key in sorted(json.keys()):
            print("{0}: {1}".format(key, json[key]))

    def print_all_json_data(self):
        json = self._get_thermostat_json()
        for key in sorted(json.keys()):
            print("{0}: {1}".format(key, json[key]))

    ########################################################################
    # Thermostat Attributes

    def get_thermostat_model(self):
        return self._get_thermostat_key("model_number")

    def get_thermostat_firmware(self):
        return self._get_thermostat_key("firmware_build_name")

    def get_thermostat_dev_build_number(self):
        return self._get_thermostat_key("dev_build_number")

    def get_thermostat_device_id(self):
        return self._get_thermostat_key("id")

    def get_thermostat_house_id(self):
        return self._get_thermostat_key("house_id")

    def get_thermostat_dealer_id(self):
        return self._get_thermostat_key("dealer_identifier")

    def get_thermostat_type(self):
        return self._get_thermostat_key("type")

    def get_thermoatat_name(self):
        return self._get_thermostat_key("name")

    ########################################################################
    # Supported Features

    def has_outdoor_temperature(self):
        return self._get_thermostat_key("have_odt")

    def has_relative_humidity(self):
        return self._get_thermostat_key("have_rh")

    def has_variable_speed_compressor(self):
        return self._get_thermostat_key("has_variable_speed_compressor")

    def has_emergency_heat(self):
        return self._get_thermostat_key("emergency_heat_supported")

    def has_variable_fan_speed(self):
        return self._get_thermostat_key("fan_type") == "VSPD"

    ########################################################################
    # System Universal Boolean Get Methods

    def is_blower_active(self):
        return self._get_thermostat_key("blower_active")

    def is_emergency_heat_active(self):
        if self.has_emergency_heat():
            return self._get_thermostat_key("emergency_heat_active")
        else:
            raise Exception("This system does not support emergency heat")

    ########################################################################
    # System Universal Get Methods

    def get_fan_mode(self):
        return self._get_thermostat_key('fan_mode')

    def get_outdoor_temperature(self):
        if self.has_outdoor_temperature():
            return self._get_thermostat_key('outdoor_temperature')
        else:
            raise Exception("This system does not have an outdoor temperature sensor")

    def get_setpoint_limits(self):
        return (self._get_thermostat_key("temperature_low_limit"), self._get_thermostat_key("temperature_high_limit"))

    def get_deadband(self):
        return self._get_thermostat_key("temperature_deadband")

    def get_relative_humidity(self):
        if self.has_relative_humidity():
            return self._get_thermostat_key("current_relative_humidity")
        else:
            raise Exception("This system does not have a relative humidity sensor.")

    def get_compressor_speed(self):
        if self.has_variable_speed_compressor():
            return self._get_thermostat_key("compressor_speed")
        else:
            raise Exception("This system does not have a variable speed compressor.")

    def get_variable_fan_speed_limits(self):
        if self.has_variable_fan_speed:
            return (self._get_thermostat_key("min_fan_speed"), self._get_thermostat_key("max_fan_speed"))

    def get_fan_speed(self):
        if self.has_variable_fan_speed():
            return self._get_thermostat_key("fan_speed")
        else:
            return 1.0 if self.is_blower_active() else 0.0

    def get_unit(self):
        return self._get_thermostat_key("scale").upper()

    def get_humidity_setpoint_limits(self):
        return (0.35, 0.65)

    def get_target_humidity(self):
        return self._get_thermostat_key('dehumidify_setpoint')

    ########################################################################
    # System Universal Set Methods

    def _get_thermostat_put_url(self, text=None):
        return "/houses/" + str(self.house_id) + "/xxl_thermostats/" + str(self.get_device_id()) + ("/" + text if text else "")

    def set_fan_mode(self, fan_mode):
        fan_mode = fan_mode.lower()
        if fan_mode in self.FAN_MODES:
            url = self._get_thermostat_put_url("fan_mode")
            data = {"fan_mode":fan_mode}
            self._put_url(url, data)
        else:
            raise KeyError("Invalid fan mode specified")

    def set_air_cleaner(self, air_cleaner_mode):
        AIR_CLEANER_MODES = ["auto", "quick", "allergy"]
        air_cleaner_mode = air_cleaner_mode.lower()
        if air_cleaner_mode in AIR_CLEANER_MODES:
            url = self._get_thermostat_put_url("air_cleaner_mode")
            data = {"air_cleaner_mode": air_cleaner_mode}
            self._put_url(url, data)
        else:
            raise KeyError("Invalid air cleaner mode specified")

    def enable_schedule(self, enabled=True):
        url = self._get_thermostat_put_url("scheduling_enabled")
        data = {"scheduling_enabled": "enabled" if enabled else "disabled"}
        self._put_url(url, data)

    def disable_schedule(self):
        self.enable_schedule(False)

    def set_emergency_heat(self, emergency_heat_on):
        if self.has_emergency_heat():
            url = self._get_thermostat_put_url("emergency_heat")
            data = {"emergency_heat_active": True if emergency_heat_on else False}
            self._put_url(url, data)
        else:
            raise Exception("This thermostat does not support emergency heat.")

    def set_target_humidity(self, humidity_level):
        if self.has_relative_humidity():
            (min_humidity, max_humidity) = self.get_humidity_setpoint_limits()

            if humidity_level >= min_humidity and humidity_level <= max_humidity:
                url = self._get_thermostat_put_url("humidity_setpoints")
                data = {"dehumidify_setpoint": humidity_level,
                        "dehumidify_allowed": True,
                        "id": self.get_device_id(),
                        "humidify_setpoint": 0.50,
                        "humidfy_allowed": False}
                self._put_url(url, data)
            else:
                raise ValueError(f"humidity_level out of range ({min_humidity} - {max_humidity})")
        else:
            raise Exception("Setting target humidity is not supported on this thermostat.")

    ########################################################################
    # Zone Methods

    def _get_zone_put_url(self, zone_id, text=None):
        zone_id = self._get_zone_key('id', zone_id)
        return "/houses/" + str(self.house_id) + "/xxl_zones/" + str(zone_id) + ("/" + text if text else "")

    def get_zone_ids(self):
        return list(range(len(self._get_thermostat_key("zones"))))

    def get_zone_name(self, zone_id=0):
        return self._get_zone_key("name", zone_id=zone_id)

    def get_zone_cooling_setpoint(self, zone_id=0):
        return self._get_zone_key('cooling_setpoint', zone_id=zone_id)

    def get_zone_heating_setpoint(self, zone_id=0):
        return self._get_zone_key('heating_setpoint', zone_id=zone_id)

    def get_zone_current_mode(self, zone_id=0):
        return self._get_zone_key("last_zone_mode", zone_id=zone_id).upper()

    def get_zone_requested_mode(self, zone_id=0):
        return self._get_zone_key("requested_zone_mode", zone_id=zone_id).upper()

    def get_zone_temperature(self, zone_id=0):
        return self._get_zone_key('temperature', zone_id=zone_id)

    def get_zone_presets(self, zone_id=0):
        # return self._get_zone_key("presets", zone_id=zone_id)
        # Can't get Nexia to return all of the presets occasionally, but I don't think there would be any other
        # "presets" available anyway...
        return self.PRESET_MODES

    def get_zone_preset(self, zone_id=0):
        return self._get_zone_key("preset_selected", zone_id=zone_id)

    def get_zone_preset_setpoints(self, preset, zone_id=0):
        index = self.get_zone_presets(zone_id).index(preset) + 1
        return(self._get_zone_key("preset_cool{0}".format(index), zone_id=zone_id),
               self._get_zone_key("preset_heat{0}".format(index), zone_id=zone_id))

    def get_zone_damper_status(self, zone_id=0):
        status = self._get_zone_key("zone_status", zone_id=zone_id)
        if len(status):
            return status
        else:
            return "Damper Closed"

    def set_zone_hold_setpoints(self, heat_temperature=None, cool_temperature=None, holdtime=0, permanent_hold=False, zone_id=0):

        return_to_schedule_holdtime = 1557432000000

        if permanent_hold is False and holdtime == 0:
            url = self._get_zone_put_url(zone_id, "return_to_schedule")
            data = {}
            self._put_url(url, data)
        else:

            heat_temperature = int(heat_temperature)
            cool_temperature = int(cool_temperature)
            deadband = self.get_deadband()
            (min_temperature, max_temperature) = self.get_setpoint_limits()

            if heat_temperature < cool_temperature and \
                    cool_temperature - heat_temperature >= deadband and \
                    heat_temperature <= max_temperature and \
                    cool_temperature >= min_temperature and \
                    holdtime >= 0:

                if permanent_hold:
                    url = self._get_zone_put_url(zone_id, "permanent_hold")
                    data = {
                        "hold_cooling_setpoint": cool_temperature,
                        "hold_heating_setpoint": heat_temperature,
                        "cooling_setpoint": cool_temperature,
                        "heating_setpoint": heat_temperature,
                        "hold_duration": holdtime,
                        "permanent_hold": permanent_hold
                    }
                else:
                    url = self._get_zone_put_url(zone_id, "hold_time_and_setpoints")
                    data = {
                        "hold_cooling_setpoint": cool_temperature,
                        "hold_heating_setpoint": heat_temperature,
                        "cooling_setpoint": cool_temperature,
                        "heating_setpoint": heat_temperature,
                        "hold_duration": holdtime,
                        "permanent_hold": permanent_hold
                    }
                self._put_url(url, data)
            else:
                raise ValueError("Temperature / hold time out of range. heat_temperature={heat}, cool_temperature={cool}, "
                                 "deadband={deadband}, min_temperature={min}, "
                                 "max_temperature={max}"
                                 "holdtime={hold}".format(heat=heat_temperature,
                                                          cool=cool_temperature,
                                                          deadband=deadband,
                                                          min=min_temperature,
                                                          max=max_temperature,
                                                          hold=holdtime
                                                          ))

    def set_zone_cool_heat_temp(self, heat_temperature=None, cool_temperature=None, set_temperature=None, zone_id=0):

        deadband = self.get_deadband()

        if set_temperature is None:
            heat_temperature = int(heat_temperature)
            cool_temperature = int(cool_temperature)
        else:
            zone_mode = self.get_zone_current_mode(zone_id)
            if zone_mode == self.OPERATION_MODE_COOL:
                cool_temperature = set_temperature
            elif zone_mode == self.OPERATION_MODE_HEAT:
                heat_temperature = set_temperature
            else:
                cool_temperature = set_temperature + math.ceil(deadband/2)
                heat_temperature = set_temperature - math.ceil(deadband/2)


        (min_temperature, max_temperature) = self.get_setpoint_limits()

        out_of_range = False
        zone_mode = self.get_zone_requested_mode(zone_id=zone_id)

        if zone_mode == self.OPERATION_MODE_AUTO:
            if heat_temperature < cool_temperature and \
                cool_temperature - heat_temperature >= deadband and \
                heat_temperature <= max_temperature and \
                cool_temperature >= min_temperature:


                url = self._get_zone_put_url(zone_id, "setpoints")

                data = {
                    'cooling_setpoint': cool_temperature,
                    'cooling_integer': str(cool_temperature),
                    'heating_setpoint': heat_temperature,
                    'heating_integer': str(heat_temperature)
                }

                self._put_url(url, data)
            else:
                out_of_range = True
        elif zone_mode == self.OPERATION_MODE_HEAT:
            if heat_temperature <= max_temperature:

                url = self._get_zone_put_url(zone_id, "setpoints")

                data = {
                    'heating_setpoint': heat_temperature,
                    'heating_integer': str(heat_temperature)
                }

                self._put_url(url, data)
            else:
                out_of_range = True
        elif zone_mode == self.OPERATION_MODE_COOL:
            if cool_temperature >= min_temperature:
                url = self._get_zone_put_url(zone_id, "setpoints")

                data = {
                    'cooling_setpoint': cool_temperature,
                    'cooling_integer': str(cool_temperature),
                }

                self._put_url(url, data)
            else:
                out_of_range = True
        else:
            # The system mode must be off
            pass

        if out_of_range:
            raise ValueError("Temperature out of range. heat_temperature={heat}, cool_temperature={cool}, "
                             "deadband={deadband}, min_temperature={min}, "
                             "max_temperature={max}".format(heat=heat_temperature,
                                                            cool=cool_temperature,
                                                            deadband=deadband,
                                                            min=min_temperature,
                                                            max=max_temperature))

    def set_zone_preset(self, preset, zone_id=0):
        # Validate the data
        if preset in self.get_zone_presets(zone_id):
            if self.get_zone_preset(zone_id) != preset:
                url = self._get_zone_put_url(zone_id, "preset")

                data = {
                    "preset_selected": preset
                }
                self._put_url(url, data)
        else:
            raise KeyError("Invalid preset")

    def set_zone_mode(self, mode, zone_id=0):
        # Validate the data
        if mode in self.OPERATION_MODES:
            url = self._get_zone_put_url(zone_id, "zone_mode")

            data = {"requested_zone_mode": mode}
            self._put_url(url, data)
        else:
            raise KeyError("Invalid mode")



