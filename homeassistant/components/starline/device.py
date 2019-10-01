from datetime import datetime
from .const import DOMAIN


class StarlineDevice():
    def __init__(self):
        self._device_id = None
        self._imei = None
        self._alias = None
        self._battery = None
        self._ctemp = None
        self._etemp = None
        self._fw_version = None
        self._gsm_lvl = None
        self._phone = None
        self._status = None
        self._ts_activity = None
        self._typename = None
        self._balance = {}  # type: dict
        self._car_state = {}  # type: dict
        self._car_alr_state = {}  # type: dict
        self._functions = {}  # type: dict
        self._position = {}  # type: dict

    def update(self, device_data):
        self._device_id = device_data["device_id"]
        self._imei = device_data["imei"]
        self._alias = device_data["alias"]
        self._battery = device_data["battery"]
        self._ctemp = device_data["ctemp"]
        self._etemp = device_data["etemp"]
        self._fw_version = device_data["fw_version"]
        self._gsm_lvl = device_data["gsm_lvl"]
        self._phone = device_data["phone"]
        self._status = device_data["status"]
        self._ts_activity = device_data["ts_activity"]
        self._typename = device_data["typename"]
        self._balance = device_data["balance"]
        self._car_state = device_data["car_state"]
        self._car_alr_state = device_data["car_alr_state"]
        self._functions = device_data["functions"]
        self._position = device_data["position"]

    @property
    def device_id(self):
        return self._device_id

    @property
    def name(self):
        return self._alias

    @property
    def position(self):
        return self._position

    @property
    def gps_attrs(self):
        return {
            'updated': datetime.utcfromtimestamp(self._position['ts']).isoformat(),
        }

    @property
    def battery_level(self):
        return self._battery

    @property
    def car_state(self):
        return self._car_state

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "manufacturer": "StarLine",
            "name": self._alias,
            "sw_version": self._fw_version,
            "model": self._typename,
        }