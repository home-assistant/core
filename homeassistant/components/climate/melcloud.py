"""
Support for MelCloud climates.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.melcloud/
"""


import logging
import time
import requests

from homeassistant.components.climate import (
    SUPPORT_FAN_MODE, SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE,
    SUPPORT_SWING_MODE, SUPPORT_TARGET_TEMPERATURE, ClimateDevice)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'melcloud'

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_FAN_MODE |
                 SUPPORT_OPERATION_MODE |
                 SUPPORT_ON_OFF |
                 SUPPORT_SWING_MODE)


OPERATION_HEAT_STR = "Heat"
OPERATION_COOL_STR = "Cool"
OPERATION_FAN_STR = "Fan"
OPERATION_AUTO_STR = "Auto"
OPERATION_OFF_STR = "Off"
OPERATION_DRY_STR = "Dry"

MELCLOUD_API_URL = "https://app.melcloud.com/Mitsubishi.Wifi.Client"


class Language:
    """List of language available."""

    English = 0
    German = 4
    Spanish = 6
    French = 7
    Italian = 19


class Mode:
    """List of mode available."""

    Heat = 1
    Dry = 2
    Cool = 3
    Fan = 7
    Auto = 8


class MelCloudAuthentication:
    """Authentication on MelCloud."""

    def __init__(self, email, password, lease_time=60):
        """Initialize the Authentication component."""
        self._email = email
        self._password = password
        self._language = Language.English
        self._lease_time = lease_time
        self._contextkey = None

    def is_login(self):
        """Return if MelCloud is logged."""
        if self._contextkey:
            return True
        return False

    def login(self):
        """Login on MelCloud."""
        _LOGGER.debug("Login ...")

        self._contextkey = None

        req = requests.post(
            MELCLOUD_API_URL + "/Login/ClientLogin",
            data={
                "Email": self._email,
                "Password": self._password,
                "Language": self._language,
                "AppVersion": "1.15.3.0",
                "Persist": False
            })

        if req.status_code == 200:
            reply = req.json()
            if "ErrorId" in reply and not reply["ErrorId"]:
                self._contextkey = reply["LoginData"]["ContextKey"]
                return True

            _LOGGER.error("Login/Password invalid ! ")
            return False

        _LOGGER.error("Login status code invalid: %d", req.status_code)
        return False

    def get_context_key(self):
        """Return the context key."""
        return self._contextkey

    def get_lease_time(self):
        """Return lease time."""
        return self._lease_time


class MelCloudDevice:
    """Representation of a Mitsubishi Device as returned by MelCloud."""

    def __init__(self, deviceid, buildingid, friendlyname, authentication):
        """Initialize the MelCloud Device."""
        self._deviceid = deviceid
        self._buildingid = buildingid
        self._friendlyname = friendlyname
        self._authentication = authentication
        self._json = None
        self._refresh_device_info()

    def __str__(self):
        """Return MelCloudDevice JSON."""
        return str(self._json)

    def _refresh_device_info(self, recursive=0):
        """Refresh the MelCloud Device informations."""
        self._json = None
        self._last_info_time = time.time()

        if recursive > 1:
            return False

        req = requests.get(
            MELCLOUD_API_URL + "/Device/Get",
            headers={
                'X-MitsContextKey': self._authentication.get_context_key()
            },
            data={
                'id': self._deviceid,
                'buildingID': self._buildingid
            })

        if req.status_code == 200:
            self._json = req.json()
            return True

        if req.status_code == 401:
            _LOGGER.error("Device information error 401 (Try to re-login...)")
            if self._authentication.login():
                return self._refresh_device_info(recursive + 1)

            return False

        _LOGGER.error("Unable to retrieve device information \
                      (Invalid status code: %d)", req.status_code)

        return False

    def _is_info_valid(self):
        """Check if information are valid."""
        if not self._json:
            return self._refresh_device_info()

        if (time.time() - self._last_info_time) >= self._authentication.\
                get_lease_time():
            _LOGGER.info("Device info lease timeout, refreshing...")
            return self._refresh_device_info()

        return True

    def apply(self, recursive=0):
        """Apply changes."""
        if not self._json:
            _LOGGER.error("Unable to apply device configuration !")
            return False

        if recursive > 1:
            return False

        # EffectiveFlags:
        # Power:          0x01
        # OperationMode:  0x02
        # Temperature:    0x04
        # FanSpeed:       0x08
        # VaneVertical:   0x10
        # VaneHorizontal: 0x100
        # Signal melcloud we want to change everything (Even if it's not true,
        # by this way we make sure the configuration is complete)
        self._json["EffectiveFlags"] = 0x1F
        self._json["HasPendingCommand"] = True

        req = requests.post(
            MELCLOUD_API_URL + "/Device/SetAta",
            headers={
                'X-MitsContextKey': self._authentication.get_context_key()
            },
            data=self._json)

        if req.status_code == 200:
            _LOGGER.info("Device configuration successfully applied")
            return True

        if req.status_code == 401:
            _LOGGER.error("Apply device configuration error 401 (Re-login...)")
            if self._authentication.login():
                return self.apply(recursive + 1)

            return False

        _LOGGER.error("Unable to apply device configuration (Invalid \
                        status code: %d)", req.status_code)

        return False

    def get_id(self):
        """Get Device ID."""
        return self._deviceid

    def get_friendly_name(self):
        """Get Device Friendly name."""
        return self._friendlyname

    def get_temperature(self):
        """Get Device Temperature."""
        if not self._is_info_valid():
            return 0

        return self._json["SetTemperature"]

    def get_room_temperature(self):
        """Get Room Temperature."""
        if not self._is_info_valid():
            return 0

        return self._json["RoomTemperature"]

    def get_fan_speed_max(self):
        """Get Maximum fan speed."""
        if not self._is_info_valid():
            return 0

        return self._json["NumberOfFanSpeeds"]

    def get_fan_speed(self):
        """Get the current fan speed: 0 Auto, 1 to NumberOfFanSpeeds."""
        if not self._is_info_valid():
            return 0

        return self._json["SetFanSpeed"]

    def get_vertical_swing_mode(self):
        """Get vertical swing mode: 0 Auto, 1 to 5, 7 Swing."""
        if not self._is_info_valid():
            return 0

        return self._json["VaneVertical"]

    def get_horizontal_swing_mode(self):
        """Get horizontal swing mode: 0 Auto, 1 to 5, 7 Swing."""
        if not self._is_info_valid():
            return 0

        return self._json["VaneHorizontal"]

    def get_mode(self):
        """Get Mode."""
        if not self._is_info_valid():
            return Mode.Auto

        return self._json["OperationMode"]

    def is_power_on(self):
        """Return if device is powerOn."""
        if not self._is_info_valid():
            return False

        return self._json["Power"]

    def is_online(self):
        """Return if device is Online."""
        if not self._is_info_valid():
            return False

        return not self._json["Offline"]

    def set_vertical_swing_mode(self, swing_mode):
        """Set vertical swing Mode."""
        if not self._is_info_valid():
            _LOGGER.error("Unable to set swing mode: %d", swing_mode)
            return False

        self._json["VaneVertical"] = swing_mode
        return True

    def set_horizontal_swing_mode(self, swing_mode):
        """Set horizontal swing Mode."""
        if not self._is_info_valid():
            _LOGGER.error("Unable to set swing mode: %d", swing_mode)
            return False

        self._json["VaneHorizontal"] = swing_mode
        return True

    def set_temperature(self, temperature):
        """Set Temperature."""
        if not self._is_info_valid():
            _LOGGER.error("Unable to set temperature: %f", temperature)
            return False

        self._json["SetTemperature"] = temperature
        return True

    # 0 Auto, 1 to NumberOfFanSpeeds
    def set_fan_speed(self, speed):
        """Set FanSpeed."""
        if not self._is_info_valid():
            _LOGGER.error("Unable to set fan speed: %d", speed)
            return False

        self._json["SetFanSpeed"] = speed
        return True

    def set_mode(self, mode):
        """Set Mode."""
        if not self._is_info_valid():
            _LOGGER.error("Unable to set mode: %d", mode)
            return

        self._json["OperationMode"] = mode

    def power_on(self):
        """Power On Device."""
        if not self._is_info_valid():
            _LOGGER.error("Unable to powerOn")
            return False

        self._json["Power"] = True
        return True

    def power_off(self):
        """Power Off Device."""
        if not self._is_info_valid():
            _LOGGER.error("Unable to powerOff")
            return False

        self._json["Power"] = False
        return True


class MelCloud:
    """Representation of a MelCloud website interface."""

    def __init__(self, authentication):
        """Initialize the MelCloud website."""
        self._authentication = authentication

    def get_devices_list(self, recursive=0):
        """Retrieve the list of devices from MelCloud website."""
        devices = []

        if recursive > 1:
            return devices

        req = requests.get(
            MELCLOUD_API_URL + "/User/ListDevices",
            headers={
                'X-MitsContextKey': self._authentication.get_context_key()
            })

        if req.status_code == 200:
            reply = req.json()

            # _LOGGER.debug(reply)
            for entry in reply:

                # Flat devices
                for device in entry["Structure"]["Devices"]:
                    devices.append(MelCloudDevice(device["DeviceID"],
                                                  device["BuildingID"],
                                                  device["DeviceName"],
                                                  self._authentication))

                # Areas devices
                for areas in entry["Structure"]["Areas"]:
                    for device in areas["Devices"]:
                        devices.append(MelCloudDevice(device["DeviceID"],
                                                      device["BuildingID"],
                                                      device["DeviceName"],
                                                      self._authentication))

                # Floor devices
                for floor in entry["Structure"]["Floors"]:
                    for device in floor["Devices"]:
                        devices.append(MelCloudDevice(device["DeviceID"],
                                                      device["BuildingID"],
                                                      device["DeviceName"],
                                                      self._authentication))

                    for areas in floor["Areas"]:
                        for device in areas["Devices"]:
                            devices.append(MelCloudDevice(device["DeviceID"],
                                                          device["BuildingID"],
                                                          device["DeviceName"],
                                                          self._authentication)
                                           )
            return devices

        if req.status_code == 401:
            _LOGGER.error("Get device list error 401 (Re-login...)")
            if self._authentication.login():
                return self.get_devices_list(recursive + 1)

            return devices

        _LOGGER.error("Unable to retrieve device list (Status code: %d)",
                      req.status_code)

        return devices


class MelCloudClimate(ClimateDevice):
    """Representation of a MelCloud HVAC."""

    def __init__(self, device):
        """Initialize the climate device."""
        self._device = device

        self._fan_list = ["Speed Auto", "Speed 1 (Min)"]
        for i in range(2, self._device.get_fan_speed_max()):
            self._fan_list.append("Speed " + str(i))
        self._fan_list.append("Speed {} (Max)".
                              format(self._device.get_fan_speed_max()))

        self._swing_list = ["Auto", "1", "2", "3", "4", "5", "Swing"]
        self._swing_id = [0, 1, 2, 3, 4, 5, 7]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE |
                SUPPORT_OPERATION_MODE | SUPPORT_ON_OFF | SUPPORT_SWING_MODE)

    @property
    def should_poll(self):
        """Request homeassistant to poll this device to refresh state."""
        return True

    @property
    def name(self):
        """Return the name of the thermostat."""
        return "MELCloud " + self._device.get_friendly_name() \
            + " (" + str(self._device.get_id()) + ")"

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_room_temperature()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.get_temperature()

    def set_temperature(self, **kwargs):
        """Set temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._device.set_temperature(kwargs.get(ATTR_TEMPERATURE))
            self._device.apply()

        self.schedule_update_ha_state()

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        for i in range(0, len(self._swing_id)):
            if self._device.get_vertical_swing_mode() == self._swing_id[i]:
                return self._swing_list[i]

        return self._swing_list[0]

    def set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        for i in range(0, len(self._swing_list)):
            if swing_mode == self._swing_list[i]:
                self._device.set_vertical_swing_mode(self._swing_id[i])
                self._device.apply()
                break

        self.schedule_update_ha_state()

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if self._device.get_fan_speed() >= len(self._fan_list):
            return self._fan_list[0]

        return self._fan_list[self._device.get_fan_speed()]

    def set_fan_mode(self, fan_mode):
        """Set fan mode."""
        for i in range(0, len(self._fan_list)):
            if fan_mode == self._fan_list[i]:
                self._device.set_fan_speed(i)
                self._device.apply()
                break

        self.schedule_update_ha_state()

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [OPERATION_HEAT_STR, OPERATION_COOL_STR, OPERATION_DRY_STR,
                OPERATION_FAN_STR, OPERATION_AUTO_STR, OPERATION_OFF_STR]

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool ..."""
        if not self._device.is_power_on():
            return OPERATION_OFF_STR
        if self._device.get_mode() == Mode.Heat:
            return OPERATION_HEAT_STR
        if self._device.get_mode() == Mode.Cool:
            return OPERATION_COOL_STR
        if self._device.get_mode() == Mode.Dry:
            return OPERATION_DRY_STR
        if self._device.get_mode() == Mode.Fan:
            return OPERATION_FAN_STR
        if self._device.get_mode() == Mode.Auto:
            return OPERATION_AUTO_STR

        # Unknown
        return ""

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode."""
        if operation_mode == OPERATION_OFF_STR:
            self._device.power_off()
        else:
            self._device.power_on()
            if operation_mode == OPERATION_HEAT_STR:
                self._device.set_mode(Mode.Heat)
            elif operation_mode == OPERATION_COOL_STR:
                self._device.set_mode(Mode.Cool)
            elif operation_mode == OPERATION_DRY_STR:
                self._device.set_mode(Mode.Dry)
            elif operation_mode == OPERATION_FAN_STR:
                self._device.set_mode(Mode.Fan)
            elif operation_mode == OPERATION_AUTO_STR:
                self._device.set_mode(Mode.Auto)

        self._device.apply()
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return is device is power on."""
        return self._device.is_power_on()

    def turn_on(self):
        """Turn on device."""
        self._device.power_on()
        self._device.apply()
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off device."""
        self._device.power_off()
        self._device.apply()
        self.schedule_update_ha_state()


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MelCloud HVAC platform."""
    _LOGGER.debug("Adding component: melcloud ...")

    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    lease_time = config.get("lease_time", 60)

    if email is None:
        _LOGGER.error("Invalid email !")
        return False

    if password is None:
        _LOGGER.error("Invalid password !")
        return False

    mcauth = MelCloudAuthentication(email, password, lease_time)
    if not mcauth.login():
        _LOGGER.error("Invalid Login/Password  !")
        return False

    mel_cloud = MelCloud(mcauth)

    device_list = []

    devices = mel_cloud.get_devices_list()
    for device in devices:
        _LOGGER.debug("Adding new device: %s", device.get_friendly_name())
        device_list.append(MelCloudClimate(device))

    add_devices(device_list)

    _LOGGER.debug("Component successfully added !")
    return True
