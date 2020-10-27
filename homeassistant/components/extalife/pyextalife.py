""" ExtaLife JSON API wrapper library. Enables device control, discovery and status fetching from EFC-01 controller """

import asyncio
from asyncio.events import AbstractEventLoop
import json
import logging
import socket

import attr

_LOGGER = logging.getLogger(__name__)

# controller info
PRODUCT_MANUFACTURER = "ZAMEL"
PRODUCT_SERIES = "Exta Life"
PRODUCT_SERIES_EXTA_FREE = "Exta Free"
PRODUCT_CONTROLLER_MODEL = "EFC-01"

MODEL_RNK22 = "RNK-22"
MODEL_RNK22_TEMP_SENSOR = "RNK-22 temperature sensor"
MODEL_RNK24 = "RNK-24"
MODEL_RNK24_TEMP_SENSOR = "RNK-24 temperature sensor"
MODEL_P4572 = "P-457/2"
MODEL_P4574 = "P-457/4"
MODEL_P4578 = "P-457/8"
MODEL_P45736 = "P457/36"
MODEL_LEDIX_P260 = "ledix touch control P260"
MODEL_ROP21 = "ROP-21"
MODEL_ROP22 = "ROP-22"
MODEL_SRP22 = "SRP-22"
MODEL_RDP21 = "RDP-21"
MODEL_GKN01 = "GKN-01"
MODEL_ROP27 = "ROP-27"
MODEL_RGT01 = "RGT-01"
MODEL_RNM24 = "RNM-24"
MODEL_RNP21 = "RNP-21"
MODEL_RNP22 = "RNP-22"
MODEL_RCT21 = "RCT-21"
MODEL_RCT22 = "RCT-22"
MODEL_ROG21 = "ROG-21"
MODEL_ROM22 = "ROM-22"
MODEL_ROM24 = "ROM-24"
MODEL_SRM22 = "SRM-22"
MODEL_SLR21 = "SLR-21"
MODEL_SLR22 = "SLR-22"
MODEL_RCM21 = "RCM-21"
MODEL_MEM21 = "MEM-21"
MODEL_RCR21 = "RCR-21"
MODEL_RCZ21 = "RCZ-21"
MODEL_SLM21 = "SLM-21"
MODEL_SLM22 = "SLM-22"
MODEL_RCK21 = "RCK-21"
MODEL_ROB21 = "ROB-21"
MODEL_P501 = "P-501"
MODEL_P520 = "P-520"
MODEL_P521L = "P-521L"
MODEL_BULIK_DRS985 = "bulik DRS-985"

# Exta Free
MODEL_ROP01 = "ROP-01"
MODEL_ROP02 = "ROP-02"
MODEL_ROM01 = "ROM-01"
MODEL_ROM10 = "ROM-10"
MODEL_ROP05 = "ROP-05"
MODEL_ROP06 = "ROP-06"
MODEL_ROP07 = "ROP-07"
MODEL_RWG01 = "RWG-01"
MODEL_ROB01 = "ROB-01"
MODEL_SRP02 = "SRP-02"
MODEL_RDP01 = "RDP-01"
MODEL_RDP02 = "RDP-02"
MODEL_RDP11 = "RDP-11"
MODEL_SRP03 = "SRP-03"

# device types string mapping
DEVICE_MAP_TYPE_TO_MODEL = {
    1: MODEL_RNK22,
    2: MODEL_RNK22_TEMP_SENSOR,
    3: MODEL_RNK24,
    4: MODEL_RNK22_TEMP_SENSOR,
    5: MODEL_P4572,
    6: MODEL_P4574,
    7: MODEL_P4578,
    8: MODEL_P45736,
    9: MODEL_LEDIX_P260,
    10: MODEL_ROP21,
    11: MODEL_ROP22,
    12: MODEL_SRP22,
    13: MODEL_RDP21,
    14: MODEL_GKN01,
    15: MODEL_ROP27,
    16: MODEL_RGT01,
    17: MODEL_RNM24,
    18: MODEL_RNP21,
    19: MODEL_RNP22,
    20: MODEL_RCT21,
    21: MODEL_RCT22,
    22: MODEL_ROG21,
    23: MODEL_ROM22,
    24: MODEL_ROM24,
    25: MODEL_SRM22,
    26: MODEL_SLR21,
    27: MODEL_SLR22,
    28: MODEL_RCM21,
    35: MODEL_MEM21,
    41: MODEL_RCR21,
    42: MODEL_RCZ21,
    45: MODEL_SLM21,
    46: MODEL_SLM22,
    47: MODEL_RCK21,
    48: MODEL_ROB21,
    51: MODEL_P501,
    52: MODEL_P520,
    53: MODEL_P521L,
    238: MODEL_BULIK_DRS985,
    # Exta Free
    326: MODEL_ROP01,
    327: MODEL_ROP02,
    328: MODEL_ROM01,
    329: MODEL_ROM10,
    330: MODEL_ROP05,
    331: MODEL_ROP06,
    332: MODEL_ROP07,
    333: MODEL_RWG01,
    334: MODEL_ROB01,
    335: MODEL_SRP02,
    336: MODEL_RDP01,
    337: MODEL_RDP02,
    338: MODEL_RDP11,
    339: MODEL_SRP03,
}

# reverse lookup
MODEL_MAP_MODEL_TO_TYPE = {v: k for k, v in DEVICE_MAP_TYPE_TO_MODEL.items()}

# device type (channel_data.data.type)
DEVICE_ARR_SENS_TEMP = [2, 4, 20, 21]
DEVICE_ARR_SENS_LIGHT = []
DEVICE_ARR_SENS_HUMID = []
DEVICE_ARR_SENS_PRESSURE = []
DEVICE_ARR_SENS_MULTI = [28]
DEVICE_ARR_SENS_WATER = [42]
DEVICE_ARR_SENS_MOTION = [41]
DEVICE_ARR_SENS_OPENCLOSE = [47]
DEVICE_ARR_SENS_ENERGY_METER = [35]
DEVICE_ARR_SENS_GATE_CONTROLLER = [48]
DEVICE_ARR_SWITCH = [10, 11, 22, 23, 24]
DEVICE_ARR_COVER = [12, 25]
DEVICE_ARR_LIGHT = [13, 26, 45, 27, 46]
DEVICE_ARR_LIGHT_RGB = []  # RGB only
DEVICE_ARR_LIGHT_RGBW = [27, 38]
DEVICE_ARR_LIGHT_EFFECT = [27, 38]
DEVICE_ARR_CLIMATE = [16]
DEVICE_ARR_REPEATER = [237]
DEVICE_ARR_TRANS_REMOTE = [5, 6, 7, 8, 51, 52, 53]
DEVICE_ARR_TRANS_NORMAL_BATTERY = [1, 3, 19]
DEVICE_ARR_TRANS_NORMAL_MAINS = [17, 18]

# Exta Free devices
DEVICE_ARR_EXTA_FREE_RECEIVER = [80]
DEVICE_ARR_EXTA_FREE_SWITCH = [326, 327, 328, 329, 330, 331, 332, 333, 334]
DEVICE_ARR_EXTA_FREE_COVER = [335, 339]
DEVICE_ARR_EXTA_FREE_LIGHT = [336, 337]
DEVICE_ARR_EXTA_FREE_RGB = [338]

DEVICE_ARR_ALL_EXFREE_SWITCH = [*DEVICE_ARR_EXTA_FREE_SWITCH]
DEVICE_ARR_ALL_EXFREE_LIGHT = [*DEVICE_ARR_EXTA_FREE_LIGHT, *DEVICE_ARR_EXTA_FREE_RGB]
DEVICE_ARR_ALL_EXFREE_COVER = [*DEVICE_ARR_EXTA_FREE_COVER]

# union of all subtypes
DEVICE_ARR_ALL_SWITCH = [*DEVICE_ARR_SWITCH, *DEVICE_ARR_ALL_EXFREE_SWITCH]
DEVICE_ARR_ALL_LIGHT = [
    *DEVICE_ARR_LIGHT,
    *DEVICE_ARR_LIGHT_RGB,
    *DEVICE_ARR_LIGHT_RGBW,
    *DEVICE_ARR_ALL_EXFREE_LIGHT,
]
DEVICE_ARR_ALL_COVER = [
    *DEVICE_ARR_COVER,
    *DEVICE_ARR_SENS_GATE_CONTROLLER,
    *DEVICE_ARR_ALL_EXFREE_COVER,
]
DEVICE_ARR_ALL_CLIMATE = [*DEVICE_ARR_CLIMATE]
DEVICE_ARR_ALL_TRANSMITTER = [
    *DEVICE_ARR_TRANS_REMOTE,
    *DEVICE_ARR_TRANS_NORMAL_BATTERY,
    *DEVICE_ARR_TRANS_NORMAL_MAINS,
]
DEVICE_ARR_ALL_IGNORE = [*DEVICE_ARR_REPEATER]

# measurable magnitude/quantity:
DEVICE_ARR_ALL_SENSOR_MEAS = [
    *DEVICE_ARR_SENS_TEMP,
    *DEVICE_ARR_SENS_HUMID,
    *DEVICE_ARR_SENS_ENERGY_METER,
]
# binary sensors:
DEVICE_ARR_ALL_SENSOR_BINARY = [
    *DEVICE_ARR_SENS_WATER,
    *DEVICE_ARR_SENS_MOTION,
    *DEVICE_ARR_SENS_OPENCLOSE,
]
DEVICE_ARR_ALL_SENSOR_MULTI = [*DEVICE_ARR_SENS_MULTI]
DEVICE_ARR_ALL_SENSOR = [
    *DEVICE_ARR_ALL_SENSOR_MEAS,
    *DEVICE_ARR_ALL_SENSOR_BINARY,
    *DEVICE_ARR_ALL_SENSOR_MULTI,
]

# list of device types mapped into `light` platform in HA
DEVICE_ICON_ARR_LIGHT = [
    15,
    13,
    8,
    9,
    14,
    16,
    17,
]  # override device and type rules based on icon; force 'light' device for some icons,


# but only when device was detected preliminarly as switch; 28 =LED


class ExtaLifeAPI:
    """ Main API class: wrapper for communication with controller """

    # Commands
    CMD_LOGIN = 1
    CMD_CONTROL_DEVICE = 20
    CMD_FETCH_RECEIVERS = 37
    CMD_FETCH_SENSORS = 38
    CMD_FETCH_TRANSMITTERS = 39
    CMD_FETCH_NETW_SETTINGS = 102
    CMD_FETCH_EXTAFREE = 203
    CMD_VERSION = 151
    CMD_RESTART = 150

    # Actions
    ACTN_TURN_ON = "TURN_ON"
    ACTN_TURN_OFF = "TURN_OFF"
    ACTN_SET_BRI = "SET_BRIGHTNESS"
    ACTN_SET_RGB = "SET_COLOR"
    ACTN_SET_POS = "SET_POSITION"
    ACTN_SET_TMP = "SET_TEMPERATURE"
    ACTN_STOP = "STOP"
    ACTN_OPEN = "UP"
    ACTN_CLOSE = "DOWN"
    ACTN_SET_SLR_MODE = "SET_MODE"
    ACTN_SET_RGT_MODE_MANUAL = "RGT_SET_MODE_MANUAL"
    ACTN_SET_RGT_MODE_AUTO = "RGT_SET_MODE_AUTO"

    # Exta Free Actions
    ACTN_EXFREE_TURN_ON_PRESS = "TURN_ON_PRESS"
    ACTN_EXFREE_TURN_ON_RELEASE = "TURN_ON_RELEASE"
    ACTN_EXFREE_TURN_OFF_PRESS = "TURN_OFF_PRESS"
    ACTN_EXFREE_TURN_OFF_RELEASE = "TURN_OFF_RELEASE"
    ACTN_EXFREE_UP_PRESS = "UP_PRESS"
    ACTN_EXFREE_UP_RELEASE = "UP_RELEASE"
    ACTN_EXFREE_DOWN_PRESS = "DOWN_PRESS"
    ACTN_EXFREE_DOWN_RELEASE = "DOWN_RELEASE"
    ACTN_EXFREE_BRIGHT_UP_PRESS = "BRIGHT_UP_PRESS"
    ACTN_EXFREE_BRIGHT_UP_RELEASE = "BRIGHT_UP_RELEASE"
    ACTN_EXFREE_BRIGHT_DOWN_PRESS = "BRIGHT_DOWN_PRESS"
    ACTN_EXFREE_BRIGHT_DOWN_RELEASE = "BRIGHT_DOWN_RELEASE"

    # Channel Types
    CHN_TYP_RECEIVERS = "receivers"
    CHN_TYP_SENSORS = "sensors"
    CHN_TYP_TRANSMITTERS = "transmitters"
    CHN_TYP_EXFREE_RECEIVERS = "exta_free_receivers"

    def __init__(
        self,
        loop: AbstractEventLoop,
        on_notification_callback=None,
        on_connect_callback=None,
        on_disconnect_callback=None,
    ):
        """API Object constructor

        on_connect - optional callback for notifications when API connects to the controller and performs successfull login

        on_disconnect - optional callback for notifications when API loses connection to the controller"""

        self.tcp: TCPAdapter = None
        self._mac = None
        self._sw_version: str = None
        self._name: str = None

        # set on_connect callback to notify caller
        self._on_connect_callback = on_connect_callback
        self._on_disconnect_callback = on_disconnect_callback
        self._on_notification_callback = on_notification_callback

        self._is_connected = False

        self._loop: AbstractEventLoop = loop

    async def async_connect(self, user, password, host=None):
        self._host = host
        self._user = user
        self._password = password

        # perform controller autodiscovery if no IP specified
        if self._host is None or self._host == "":
            self._host = await self._loop.run_in_executor(
                None, TCPAdapter.discover_controller
            )

        # check if still None after autodiscovery
        if not self._host:
            raise TCPConnError("Could not find controller IP via autodiscovery")

        ConnectionParams.host = self._host
        ConnectionParams.user = self._user
        ConnectionParams.password = self._password
        ConnectionParams.eventloop = self._loop
        ConnectionParams.keepalive = 8  # ping period; in seconds
        ConnectionParams.on_notification_callback = self._async_on_notification_callback
        ConnectionParams.on_connect_callback = (
            self._async_on_tcp_connect_callback
        )  # self._on_connect_callback
        ConnectionParams.on_disconnect_callback = self._async_on_tcp_disconnect_callback

        # init TCP adapter and try to connect
        self._connection = TCPAdapter(ConnectionParams)

        # connect and login - may raise TCPConnErr
        _LOGGER.debug("Connecting to controller using IP: %s", self._host)
        await self._connection.async_connect()

        resp = await self._connection.async_login()

        # check response if login succeeded
        if resp[0]["status"] != "success":
            raise TCPConnError(resp)

        # determine controller MAC as its unique identifier
        self._mac = await self.async_get_mac()

        return True

    async def async_reconnect(self):
        """ Reconnect with existing connection parameters """
        return await self.async_connect(self._user, self._password, self._host)

    @property
    def host(self):
        return self._host

    async def _async_on_tcp_connect_callback(self):
        """ Called when connectivity is (re)established and logged on successfully """
        self._is_connected = True
        # refresh software version info
        await self.async_get_version_info()
        await self.async_get_name()

        if self._on_connect_callback is not None:
            await self._loop.run_in_executor(None, self._on_connect_callback)

    async def _async_on_tcp_disconnect_callback(self):
        """ Called when connectivity is lost """
        self._is_connected = False

        if self._on_disconnect_callback is not None:
            await self._loop.run_in_executor(None, self._on_disconnect_callback)

    async def _async_on_notification_callback(self, data):
        """ Called when notification from the controller is received """
        if (
            self._on_notification_callback(data) is not None
            and data.get("command") == self.CMD_CONTROL_DEVICE
        ):
            # forward only device status changes to the listener
            self._on_notification_callback(data)

    def set_notification_callback(self, callback):
        """ update Notification callback assignment """
        self._on_notification_callback = callback

    @property
    def is_connected(self) -> bool:
        """ Returns True or False depending of the connection is alive and user is logged on """
        return self._is_connected

    @classmethod
    def discover_controller(cls):
        """ Returns controller IP address if found, otherwise None"""
        return TCPAdapter.discover_controller()

    @property
    def sw_version(self) -> str:
        return self._sw_version

    async def async_get_version_info(self):
        """ Get controller software version """
        cmd_data = {"data": None}
        try:
            resp = await self._connection.async_execute_command(
                self.CMD_VERSION, cmd_data
            )
            self._sw_version = resp[0]["data"]["new_version"]
            return self._sw_version

        except TCPCmdError:
            _LOGGER.error("Command %s could not be executed", self.CMD_VERSION)
            return

    async def async_get_mac(self):
        from getmac import get_mac_address

        # get EFC-01 controller MAC address
        return await self._loop.run_in_executor(None, get_mac_address, None, self._host)

    @property
    def mac(self):
        return self._mac

    async def async_get_network_settings(self):
        """ Executes command 102 to get network settings and controller name """
        try:
            cmd = self.CMD_FETCH_NETW_SETTINGS
            resp = await self._connection.async_execute_command(cmd, None)
            return resp[0].get("data")

        except TCPCmdError:
            _LOGGER.error("Command %s could not be executed", cmd)
            return None

    async def async_get_name(self):
        """ Get controller name """
        data = await self.async_get_network_settings()
        self._name = data.get("name") if data else None
        return self._name

    @property
    def name(self) -> str:
        """ Get controller name from buffer """
        return self._name

    async def async_get_channels(
        self,
        include=(
            CHN_TYP_RECEIVERS,
            CHN_TYP_SENSORS,
            CHN_TYP_TRANSMITTERS,
            CHN_TYP_EXFREE_RECEIVERS,
        ),
    ):
        """
        Get list of dicts of Exta Life channels consisting of native Exta Life TCP JSON
        data, but with transformed data model. Each channel will have native channel info
        AND device info. 2 channels of the same device will have the same device attributes
        """
        try:
            channels = list()
            if self.CHN_TYP_RECEIVERS in include:
                cmd = self.CMD_FETCH_RECEIVERS
                resp = await self._connection.async_execute_command(cmd, None)
                # here is where the magic happens - transform TCP JSON data into API channel representation
                channels.extend(self._get_channels_int(resp))

            if self.CHN_TYP_SENSORS in include:
                cmd = self.CMD_FETCH_SENSORS
                resp = await self._connection.async_execute_command(cmd, None)
                channels.extend(self._get_channels_int(resp))

            if self.CHN_TYP_TRANSMITTERS in include:
                cmd = self.CMD_FETCH_TRANSMITTERS
                resp = await self._connection.async_execute_command(cmd, None)
                channels.extend(self._get_channels_int(resp, dummy_ch=True))

            if self.CHN_TYP_EXFREE_RECEIVERS in include:
                cmd = self.CMD_FETCH_EXTAFREE
                resp = await self._connection.async_execute_command(cmd, None)
                channels.extend(self._get_channels_int(resp))

            return channels

        except TCPCmdError:
            _LOGGER.error("Command %s could not be executed", cmd)
            return None

    @classmethod
    def _get_channels_int(cls, data_js, dummy_ch=False):

        def_channel = None
        if dummy_ch:
            def_channel = "#"
        channels = []  # list of JSON dicts
        for cmd in data_js:
            for device in cmd["data"]["devices"]:
                dev = device.copy()

                if dev.get("exta_free_device"):
                    dev["type"] = (
                        int(dev["state"][0]["exta_free_type"]) + 300
                    )  # do the same as the Exta Life app does - add 300
                    # to move identifiers to Exta Life "namespace"

                dev.pop("state")
                for state in device["state"]:
                    ch_no = (
                        state.get("channel", def_channel)
                        if def_channel
                        else state["channel"]
                    )
                    channel = {
                        # API channel, not TCP channel
                        "id": str(device["id"])
                        + "-"
                        + str(state.get("channel", def_channel)),
                        "data": {**state, **dev},
                    }
                    channels.append(channel)
        return channels

    async def async_execute_action(self, action, channel_id, **fields):
        """Execute action/command in controller
        action - action to be performed. See ACTN_* constants
        channel_id - concatenation of device id and channel number e.g. '1-1'
        **fields - fields of the native JSON command e.g. value, mode, mode_val etc

        Returns array of dicts converted from JSON or None if error occured
        """
        MAP_ACION_STATE = {
            # Exta Life:
            ExtaLifeAPI.ACTN_TURN_ON: 1,
            ExtaLifeAPI.ACTN_TURN_OFF: 0,
            ExtaLifeAPI.ACTN_OPEN: 1,
            ExtaLifeAPI.ACTN_CLOSE: 0,
            ExtaLifeAPI.ACTN_STOP: 2,
            ExtaLifeAPI.ACTN_SET_POS: None,
            ExtaLifeAPI.ACTN_SET_RGT_MODE_AUTO: 0,
            ExtaLifeAPI.ACTN_SET_RGT_MODE_MANUAL: 1,
            ExtaLifeAPI.ACTN_SET_TMP: 1,
            # Exta Free:
            ExtaLifeAPI.ACTN_EXFREE_TURN_ON_PRESS: 1,
            ExtaLifeAPI.ACTN_EXFREE_TURN_ON_RELEASE: 2,
            ExtaLifeAPI.ACTN_EXFREE_TURN_OFF_PRESS: 3,
            ExtaLifeAPI.ACTN_EXFREE_TURN_OFF_RELEASE: 4,
            ExtaLifeAPI.ACTN_EXFREE_UP_PRESS: 1,
            ExtaLifeAPI.ACTN_EXFREE_UP_RELEASE: 2,
            ExtaLifeAPI.ACTN_EXFREE_DOWN_PRESS: 3,
            ExtaLifeAPI.ACTN_EXFREE_DOWN_RELEASE: 4,
            ExtaLifeAPI.ACTN_EXFREE_BRIGHT_UP_PRESS: 1,
            ExtaLifeAPI.ACTN_EXFREE_BRIGHT_UP_RELEASE: 2,
            ExtaLifeAPI.ACTN_EXFREE_BRIGHT_DOWN_PRESS: 3,
            ExtaLifeAPI.ACTN_EXFREE_BRIGHT_DOWN_RELEASE: 4,
        }
        ch_id, channel = channel_id.split("-")
        ch_id = int(ch_id)
        channel = int(channel)

        cmd_data = {
            "id": ch_id,
            "channel": channel,
            "state": MAP_ACION_STATE.get(action),
        }
        # this assumes the right fields are passed to the API
        cmd_data.update(**fields)

        try:
            cmd = self.CMD_CONTROL_DEVICE
            resp = await self._connection.async_execute_command(cmd, cmd_data)

            _LOGGER.debug("JSON response for command %s: %s", cmd, resp)

            return resp
        except TCPCmdError as err:
            # _LOGGER.error("Command %s could not be executed", cmd)
            _LOGGER.exception(err)
            return None

    async def async_restart(self):
        """ Restart EFC-01 """
        try:
            cmd = self.CMD_RESTART
            cmd_data = dict()

            resp = await self._connection.async_execute_command(cmd, cmd_data)

            _LOGGER.debug("JSON response for command %s: %s", cmd, resp)

            return resp
        except TCPCmdError:
            _LOGGER.error("Command %s could not be executed", cmd)
            return None

    async def disconnect(self):
        """ Disconnect from the controller and stop message tasks """
        await self._connection.async_stop(True)

    def get_tcp_adapter(self):
        return self._connection


class TCPConnError(Exception):
    def __init__(self, data=None, previous=None):
        super().__init__()
        self.data = data
        self.error_code = None
        self.previous = previous
        if data:
            data = data[-1].get("data") if isinstance(data[-1], dict) else None
            self.error_code = None if not data else data.get("code")


class TCPCmdError(Exception):
    def __init__(self, data=None):
        super().__init__()
        self.data = data
        self.error_code = None
        if data:
            data = data[-1].get("data") if isinstance(data[-1], dict) else None
            self.error_code = None if not data else data.get("code")


@attr.s
class ConnectionParams:
    eventloop = attr.ib(type=asyncio.events.AbstractEventLoop)
    host = attr.ib(type=str)
    user = attr.ib(type=str)
    password = attr.ib(type=str)
    on_connect_callback = None
    on_disconnect_callback = None
    on_notification_callback = None
    keepalive = attr.ib(type=float)


class APIMessage:
    def __init__(self):
        self.command = ""
        self.data = dict()


class APIRequest(APIMessage):
    def __init__(self, command: str, data: dict):
        super().__init__()
        self.command = command
        self.data = data

    # def from_dict(self, request: dict):
    #     self.command = request.get("command")
    #     self.data = request.get("data")

    def as_dict(self):
        return {"command": self.command, "data": self.data}

    def as_json(self):
        return json.dumps(self.as_dict())


class APIResponse(APIMessage):
    def __init__(self, json: dict):
        super().__init__()
        self._as_dict = json
        self.command = json.get("command")
        self.data = json.get("data")
        self.status = json.get("status")

    @classmethod
    def from_json(cls, json_str: str):
        # print(json_str[:-1])
        json_dict = json.loads(json_str[:-1])

        return APIResponse(json_dict)

    def as_dict(self):
        return self._as_dict


class TCPAdapter:
    TCP_BUFF_SIZE = 8192
    EFC01_PORT = 20400

    _cmd_in_execution = False

    def __init__(self, params: ConnectionParams):

        from datetime import datetime

        self._params = params
        self.user = None
        self.password = None
        self.host = None

        self._on_connect_callback = params.on_connect_callback
        self._on_disconnect_callback = params.on_disconnect_callback

        self.tcp = None

        self._connected = False
        self._stopped = False
        self._authenticated = False
        self._tcp_reader: asyncio.StreamReader = (
            None
        )  # type: Optional[asyncio.StreamReader]
        self._tcp_writer: asyncio.StreamWriter = (
            None
        )  # type: Optional[asyncio.StreamWriter]
        self._write_lock = asyncio.Lock()
        self._cmd_exec_lock = asyncio.Lock()
        self._running_task = None
        self._socket = None
        self._socket_connected = False
        self._ping_task = None

        self._tcp_last_write = datetime.now()

        self._message_handlers = []

    def _start_ping(self) -> None:
        """ Perform "smart" ping task. Send ping if nothing was send to socket in the last keepalive-time period """

        self._ping_task = self._params.eventloop.create_task(self._ping_())

    async def _ping_(self) -> None:
        from datetime import datetime, timedelta

        while self._connected:
            last_write = (datetime.now() - self._tcp_last_write).seconds

            if last_write < self._params.keepalive:
                period = self._params.keepalive - last_write
                await asyncio.sleep(period)
                continue

            if not self._connected:
                break

            try:
                await self.async_ping()
            except TCPConnError:
                _LOGGER.error("%s: Ping Failed!", self._params.address)
                await self._async_on_error()
                break

        _LOGGER.debug("_ping_() - task ends")

    async def async_ping(self) -> None:
        self._check_connected()
        msg = " " + chr(3)
        await self.async_send_message(msg.encode())

    async def _async_write(self, data: bytes) -> None:
        from datetime import datetime

        if not self._socket_connected:
            raise TCPConnError("Socket is not connected")
        try:
            async with self._write_lock:
                self._tcp_writer.write(data)
                self._tcp_last_write = datetime.now()
                await self._tcp_writer.drain()
        except OSError as err:
            await self._async_on_error()
            raise TCPConnError(f"Error while writing data: {err}")

    async def async_send_message(self, msg) -> None:

        _LOGGER.debug("Sending:  %s", str(msg))
        await self._async_write(bytes(msg))

    async def async_send_message_await_response(
        self, send_msg, command: str, timeout: float = 30.0
    ):  # -> Any:
        """ Send message to controller and await response """
        # prevent controller overloading and command loss - wait until finished (lock released)
        async with self._cmd_exec_lock:
            fut = self._params.eventloop.create_future()
            responses = []

            def on_message(resp: APIResponse):
                _LOGGER.debug("on_message(), resp: %s", resp.as_dict())
                if fut.done():
                    return

                if resp.command != command:
                    return

                if resp.status == "searching":
                    responses.append(resp.as_dict())
                elif resp.status in ("success", "failure", "partial"):
                    responses.append(resp.as_dict())
                    fut.set_result(responses)

            self._message_handlers.append(on_message)
            await self.async_send_message(send_msg)

            try:
                await asyncio.wait_for(fut, timeout)

            except asyncio.TimeoutError:
                if self._stopped:
                    raise TCPConnError("Disconnected while waiting for API response!")
                await self._async_on_error()
                raise TCPConnError("Timeout while waiting for API response!")

            try:
                self._message_handlers.remove(on_message)
            except ValueError:
                pass

            return responses
            # return

    async def async_execute_command(self, command: str, data) -> list:

        # request = {"command": command, "data": data}
        # req = self._json_to_tcp(request)
        req = APIRequest(command, data)
        msg = str(req.as_json() + chr(3)).encode()
        response = await self.async_send_message_await_response(msg, command)

        if len(response) == 0:
            raise TCPConnError("No response received from Controller!")

        return response

    async def _async_recv(self) -> bytes:

        try:
            ret = await self._tcp_reader.readuntil(chr(3).encode())
        except (asyncio.IncompleteReadError, OSError, TimeoutError) as err:
            raise TCPConnError(f"Error while receiving data: {err}")

        return ret

    def _check_connected(self) -> None:
        if not self._connected:
            raise TCPConnError("Not connected!")

    async def _close_socket(self) -> None:
        _LOGGER.debug("entering _close_socket()")
        from datetime import datetime

        if not self._socket_connected:
            return
        async with self._write_lock:
            self._tcp_writer.close()
            self._tcp_writer = None
            self._tcp_reader = None
        if self._socket is not None:
            self._socket.close()

        self._socket_connected = False
        self._connected = False
        self._authenticated = False
        _LOGGER.debug("%s: Closed socket", self._params.host)

    async def async_connect(self):
        """
        Connect to EFC-01 via TCP socket
        """
        if self._stopped:
            raise TCPConnError("Connection is closed!")
        if self._connected:
            raise TCPConnError("Already connected!")

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setblocking(False)
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        _LOGGER.debug("Connecting to %s:%s", self._params.host, self.EFC01_PORT)
        try:
            coro = self._params.eventloop.sock_connect(
                self._socket, (self._params.host, self.EFC01_PORT)
            )
            await asyncio.wait_for(coro, 30.0)
        except OSError as err:
            await self._async_on_error()
            raise TCPConnError(
                f"Error connecting to {self._params.host}: {err}", previous=err
            )
        except asyncio.TimeoutError:
            await self._async_on_error()
            raise TCPConnError(f"Timeout while connecting to {self._params.host}")

        _LOGGER.debug("%s: Opened socket for", self._params.host)
        self._tcp_reader, self._tcp_writer = await asyncio.open_connection(
            sock=self._socket
        )
        self._socket_connected = True
        self._params.eventloop.create_task(self.async_run_forever())

        _LOGGER.debug("Successfully connected ")

        self._connected = True

        self._start_ping()

    async def async_login(self) -> None:
        """
        Try to log on via command: 1
        return json dictionary with result or exception in case of connection or logon
        problem
        """

        self._check_connected()
        if self._authenticated:
            raise TCPConnError("Already logged in!")

        _LOGGER.debug(
            "Logging in...user: %s, password: %s",
            self._params.user,
            self._params.password,
        )
        resp_js = await self.async_execute_command(
            ExtaLifeAPI.CMD_LOGIN,
            {"password": self._params.password, "login": self._params.user},
        )

        if (
            resp_js[0].get("status") == "failure"
            and resp_js[0].get("data").get("code") == -2
        ):
            # pass
            raise TCPConnError("Invalid password!")

        self._authenticated = True

        _LOGGER.debug("Authenticated")

        await self._async_event_connect()

        return resp_js

    async def async_run_forever(self) -> None:
        while True:
            try:
                await self._async_run_once()
            except TCPConnError as err:
                _LOGGER.info("Error while reading incoming messages: %s", err.data)
                await self._async_on_error()
                break
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.info(
                    "Unexpected error while reading incoming messages: %s", err
                )
                await self._async_on_error()
                break

        _LOGGER.debug("async_run_forever() - task ends")

    async def _async_run_once(self) -> None:

        raw_msg = await self._async_recv()

        msg = raw_msg.decode()

        resp = APIResponse.from_json(msg)
        _LOGGER.debug("_async_run_once, msg: %s", msg)

        for msg_handler in self._message_handlers[:]:
            msg_handler(resp)

        await self._handle_notification(resp)

    async def _handle_notification(self, resp: APIResponse):
        _LOGGER.debug("_handle_notification(), resp: %s", resp.as_dict())

        # pass only status change notifications to registered listeners
        if (
            resp.status == "notification"
            and self._params.on_notification_callback is not None
        ):
            await self._params.on_notification_callback(resp.as_dict())

    async def _async_on_error(self) -> None:
        await self.async_stop(force=True)

    async def async_stop(self, force: bool = False) -> None:
        _LOGGER.debug("async_stop() self._stopped: %s", self._stopped)
        if self._stopped:
            return

        self._stopped = True
        if self._running_task is not None:
            self._running_task.cancel()

        if self._ping_task is not None:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        await self._close_socket()

        await self._async_event_disconnect()

    async def _async_event_connect(self):
        """ Notify of (re)connection by calling provided callback """
        if self._on_connect_callback is not None:
            await self._on_connect_callback()

    async def _async_event_disconnect(self):
        """ Notify of lost connection by calling provided callback """
        if self._on_disconnect_callback is not None:
            await self._on_disconnect_callback()

    @staticmethod
    def discover_controller():
        """
        Perform controller autodiscovery using UDP query
        return IP as string or false if not found
        """
        MCAST_GRP = "225.0.0.1"
        MCAST_PORT = 20401
        import struct

        # sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_address = ("", MCAST_PORT)

        # Create the socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Bind to the server address
        try:
            sock.bind(server_address)
        except OSError as e:
            sock.close()
            sock = None
            _LOGGER.error(
                "Could not connect to receive UDP multicast from EFC-01 on port %s",
                MCAST_PORT,
            )
            return False
        # Tell the operating system to add the socket to the multicast group
        # on all interfaces (join multicast group)
        group = socket.inet_aton(MCAST_GRP)
        mreq = struct.pack("4sL", group, socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        sock.settimeout(3)
        try:
            data, address = sock.recvfrom(1024)
        except Exception:
            sock.close()
            return
        sock.close()
        _LOGGER.debug("Got multicast response from EFC-01: %s", str(data.decode()))
        if data == b'{"status":"broadcast","command":0,"data":null}\x03':
            return address[0]  # return IP - array[0]; array[1] is sender's port
        return
