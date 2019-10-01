from datetime import datetime
from .const import (DOMAIN, BATTERY_LEVEL_MIN, BATTERY_LEVEL_MAX,
                    GSM_LEVEL_MIN, GSM_LEVEL_MAX)


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
    def battery_level_percent(self):
        return round((self._battery - BATTERY_LEVEL_MIN) / (BATTERY_LEVEL_MAX - BATTERY_LEVEL_MIN) * 100)

    @property
    def balance(self):
        return self._balance["active"]

    @property
    def car_state(self):
        return self._car_state

    @property
    def alarm_state(self):
        return self._car_alr_state

    @property
    def temp_inner(self):
        return self._ctemp

    @property
    def temp_engine(self):
        return self._etemp

    @property
    def gsm_level(self):
        return self._gsm_lvl

    @property
    def imei(self):
        return self._imei

    @property
    def phone(self):
        return self._phone

    @property
    def gsm_level_percent(self):
        return round((self._gsm_lvl - GSM_LEVEL_MIN) / (GSM_LEVEL_MAX - GSM_LEVEL_MIN) * 100)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "manufacturer": "StarLine",
            "name": self._alias,
            "sw_version": self._fw_version,
            "model": self._typename,
        }