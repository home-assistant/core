from datetime import datetime
from typing import Optional, Dict, Any, List
from .const import (DOMAIN, BATTERY_LEVEL_MIN, BATTERY_LEVEL_MAX,
                    GSM_LEVEL_MIN, GSM_LEVEL_MAX)


class StarlineDevice():
    """StarLine device."""

    def __init__(self):
        """Constructor."""

        self._device_id: Optional[str] = None
        self._imei: Optional[str] = None
        self._alias: Optional[str] = None
        self._battery: Optional[int] = None
        self._ctemp: Optional[int] = None
        self._etemp: Optional[int] = None
        self._fw_version: Optional[str] = None
        self._gsm_lvl: Optional[int] = None
        self._phone: Optional[str] = None
        self._status: Optional[int] = None  # TODO: cast to boolean
        self._ts_activity: Optional[float] = None
        self._typename: Optional[str] = None
        self._balance: Dict[str, Dict[str, Any]] = {}
        self._car_state: Dict[str, bool] = {}
        self._car_alr_state: Dict[str, bool] = {}
        self._functions: List[str] = []
        self._position: Dict[str, float] = {}

    def update(self, device_data):
        """Update data from server."""
        self._device_id = str(device_data["device_id"])
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

    def update_car_state(self, car_state):
        """Update car state from server."""
        for key in car_state:
            if key in self._car_state:
                self._car_state[key] = car_state[key] in ["1", "true", True]

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
    def balance_attrs(self):
        return {
            "operator": self.balance["operator"],
            "state": self.balance["state"],
            "updated": self.balance["ts"],
        }

    @property
    def gsm_attrs(self):
        return {
            "raw": self._gsm_lvl,
            "imei": self._imei,
            "phone": self._phone,
        }

    @property
    def engine_attrs(self):
        return {
            "autostart": self._car_state["r_start"],
            "ignition": self._car_state["run"],
        }

    @property
    def battery_level(self):
        return self._battery

    @property
    def battery_level_percent(self):
        if self._battery > BATTERY_LEVEL_MAX:
            return 100
        if self._battery < BATTERY_LEVEL_MIN:
            return 0
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
        if self._gsm_lvl > GSM_LEVEL_MAX:
            return 100
        if self._gsm_lvl < GSM_LEVEL_MIN:
            return 0
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