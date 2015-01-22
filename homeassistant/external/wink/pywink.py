__author__ = 'JOHNMCL'

import json
import time

import requests

baseUrl = "https://winkapi.quirky.com"

headers = {}


class wink_sensor_pod(object):
    """ represents a wink.py sensor
    json_obj holds the json stat at init (and if there is a refresh it's updated
    it's the native format for this objects methods
    and looks like so:
{
    "data": {
        "last_event": {
            "brightness_occurred_at": None,
            "loudness_occurred_at": None,
            "vibration_occurred_at": None
        },
        "model_name": "Tripper",
        "capabilities": {
            "sensor_types": [
                {
                    "field": "opened",
                    "type": "boolean"
                },
                {
                    "field": "battery",
                    "type": "percentage"
                }
            ]
        },
        "manufacturer_device_model": "quirky_ge_tripper",
        "location": "",
        "radio_type": "zigbee",
        "manufacturer_device_id": None,
        "gang_id": None,
        "sensor_pod_id": "37614",
        "subscription": {
        },
        "units": {
        },
        "upc_id": "184",
        "hidden_at": None,
        "last_reading": {
            "battery_voltage_threshold_2": 0,
            "opened": False,
            "battery_alarm_mask": 0,
            "opened_updated_at": 1421697092.7347496,
            "battery_voltage_min_threshold_updated_at": 1421697092.7347229,
            "battery_voltage_min_threshold": 0,
            "connection": None,
            "battery_voltage": 25,
            "battery_voltage_threshold_1": 25,
            "connection_updated_at": None,
            "battery_voltage_threshold_3": 0,
            "battery_voltage_updated_at": 1421697092.7347066,
            "battery_voltage_threshold_1_updated_at": 1421697092.7347302,
            "battery_voltage_threshold_3_updated_at": 1421697092.7347434,
            "battery_voltage_threshold_2_updated_at": 1421697092.7347374,
            "battery": 1.0,
            "battery_updated_at": 1421697092.7347553,
            "battery_alarm_mask_updated_at": 1421697092.734716
        },
        "triggers": [
        ],
        "name": "MasterBathroom",
        "lat_lng": [
            37.550773,
            -122.279182
        ],
        "uuid": "a2cb868a-dda3-4211-ab73-fc08087aeed7",
        "locale": "en_us",
        "device_manufacturer": "quirky_ge",
        "created_at": 1421523277,
        "local_id": "2",
        "hub_id": "88264"
    },
}

     """
    def __init__(self, aJSonObj, objectprefix="sensor_pods"):
        self.jsonState = aJSonObj
        self.objectprefix = objectprefix

    def __str__(self):
        return "%s %s %s" % (self.name(), self.deviceId(), self.state())

    def __repr__(self):
        return "<Wink sensor %s %s %s>" % (self.name(), self.deviceId(), self.state())

    @property
    def _last_reading(self):
        return self.jsonState.get('last_reading') or {}

    def name(self):
        return self.jsonState.get('name', "Unknown Name")

    def state(self):
        return self._last_reading.get('opened', False)

    def deviceId(self):
        return self.jsonState.get('sensor_pod_id', self.name())

    def refresh_state_at_hub(self):
        """
        Tell hub to query latest status from device and upload to Wink.
        PS: Not sure if this even works..
        """
        urlString = baseUrl + "/%s/%s/refresh" % (self.objectprefix, self.deviceId())
        requests.get(urlString, headers=headers)

    def updateState(self):
        """ Update state with latest info from Wink API. """
        urlString = baseUrl + "/%s/%s" % (self.objectprefix, self.deviceId())
        arequest = requests.get(urlString, headers=headers)
        self._updateStateFromResponse(arequest.json())

    def _updateStateFromResponse(self, response_json):
        """
        :param response_json: the json obj returned from query
        :return:
        """
        self.jsonState = response_json.get('data')

class wink_binary_switch(object):
    """ represents a wink.py switch
    json_obj holds the json stat at init (and if there is a refresh it's updated
    it's the native format for this objects methods
    and looks like so:

{
    "data": {
        "binary_switch_id": "4153",
        "name": "Garage door indicator",
        "locale": "en_us",
        "units": {},
        "created_at": 1411614982,
        "hidden_at": null,
        "capabilities": {},
        "subscription": {},
        "triggers": [],
        "desired_state": {
            "powered": false
        },
        "manufacturer_device_model": "leviton_dzs15",
        "manufacturer_device_id": null,
        "device_manufacturer": "leviton",
        "model_name": "Switch",
        "upc_id": "94",
        "gang_id": null,
        "hub_id": "11780",
        "local_id": "9",
        "radio_type": "zwave",
        "last_reading": {
            "powered": false,
            "powered_updated_at": 1411614983.6153464,
            "powering_mode": null,
            "powering_mode_updated_at": null,
            "consumption": null,
            "consumption_updated_at": null,
            "cost": null,
            "cost_updated_at": null,
            "budget_percentage": null,
            "budget_percentage_updated_at": null,
            "budget_velocity": null,
            "budget_velocity_updated_at": null,
            "summation_delivered": null,
            "summation_delivered_updated_at": null,
            "sum_delivered_multiplier": null,
            "sum_delivered_multiplier_updated_at": null,
            "sum_delivered_divisor": null,
            "sum_delivered_divisor_updated_at": null,
            "sum_delivered_formatting": null,
            "sum_delivered_formatting_updated_at": null,
            "sum_unit_of_measure": null,
            "sum_unit_of_measure_updated_at": null,
            "desired_powered": false,
            "desired_powered_updated_at": 1417893563.7567682,
            "desired_powering_mode": null,
            "desired_powering_mode_updated_at": null
        },
        "current_budget": null,
        "lat_lng": [
            38.429996,
            -122.653721
        ],
        "location": "",
        "order": 0
    },
    "errors": [],
    "pagination": {}
}

     """
    def __init__(self, aJSonObj, objectprefix="binary_switches"):
        self.jsonState = aJSonObj
        self.objectprefix = objectprefix
        # Tuple (desired state, time)
        self._last_call = (0, None)

    def __str__(self):
        return "%s %s %s" % (self.name(), self.deviceId(), self.state())

    def __repr__(self):
        return "<Wink switch %s %s %s>" % (self.name(), self.deviceId(), self.state())

    @property
    def _last_reading(self):
        return self.jsonState.get('last_reading') or {}

    def name(self):
        return self.jsonState.get('name', "Unknown Name")

    def state(self):
        # Optimistic approach to setState:
        # Within 15 seconds of a call to setState we assume it worked.
        if self._recent_state_set():
            return self._last_call[1]

        return self._last_reading.get('powered', False)

    def deviceId(self):
        return self.jsonState.get('binary_switch_id', self.name())

    def setState(self, state):
        """
        :param state:   a boolean of true (on) or false ('off')
        :return: nothing
        """
        urlString = baseUrl + "/%s/%s" % (self.objectprefix, self.deviceId())
        values = {"desired_state": {"powered": state}}
        arequest = requests.put(urlString, data=json.dumps(values), headers=headers)
        self._updateStateFromResponse(arequest.json())

        self._last_call = (time.time(), state)

    def refresh_state_at_hub(self):
        """
        Tell hub to query latest status from device and upload to Wink.
        PS: Not sure if this even works..
        """
        urlString = baseUrl + "/%s/%s/refresh" % (self.objectprefix, self.deviceId())
        requests.get(urlString, headers=headers)

    def updateState(self):
        """ Update state with latest info from Wink API. """
        urlString = baseUrl + "/%s/%s" % (self.objectprefix, self.deviceId())
        arequest = requests.get(urlString, headers=headers)
        self._updateStateFromResponse(arequest.json())

    def wait_till_desired_reached(self):
        """ Wait till desired state reached. Max 10s. """
        if self._recent_state_set():
            return

        # self.refresh_state_at_hub()
        tries = 1

        while True:
            self.updateState()
            last_read = self._last_reading

            if last_read.get('desired_powered') == last_read.get('powered') \
               or tries == 5:
                break

            time.sleep(2)

            tries += 1
            self.updateState()
            last_read = self._last_reading

    def _updateStateFromResponse(self, response_json):
        """
        :param response_json: the json obj returned from query
        :return:
        """
        self.jsonState = response_json.get('data')

    def _recent_state_set(self):
        return time.time() - self._last_call[0] < 15


class wink_bulb(wink_binary_switch):
    """ represents a wink.py bulb
    json_obj holds the json stat at init (and if there is a refresh it's updated
    it's the native format for this objects methods
    and looks like so:

     "light_bulb_id": "33990",
    "name": "downstaurs lamp",
    "locale": "en_us",
    "units":{},
    "created_at": 1410925804,
    "hidden_at": null,
    "capabilities":{},
    "subscription":{},
    "triggers":[],
    "desired_state":{"powered": true, "brightness": 1},
    "manufacturer_device_model": "lutron_p_pkg1_w_wh_d",
    "manufacturer_device_id": null,
    "device_manufacturer": "lutron",
    "model_name": "Caseta Wireless Dimmer & Pico",
    "upc_id": "3",
    "hub_id": "11780",
    "local_id": "8",
    "radio_type": "lutron",
    "linked_service_id": null,
    "last_reading":{
    "brightness": 1,
    "brightness_updated_at": 1417823487.490747,
    "connection": true,
    "connection_updated_at": 1417823487.4907365,
    "powered": true,
    "powered_updated_at": 1417823487.4907532,
    "desired_powered": true,
    "desired_powered_updated_at": 1417823485.054675,
    "desired_brightness": 1,
    "desired_brightness_updated_at": 1417409293.2591703
    },
    "lat_lng":[38.429962, -122.653715],
    "location": "",
    "order": 0

     """
    jsonState = {}

    def __init__(self, ajsonobj):
        super().__init__(ajsonobj, "light_bulbs")

    def deviceId(self):
        return self.jsonState.get('light_bulb_id', self.name())

    def brightness(self):
        return self._last_reading.get('brightness')

    def setState(self, state, brightness=None):
        """
        :param state:   a boolean of true (on) or false ('off')
        :return: nothing
        """
        urlString = baseUrl + "/light_bulbs/%s" % self.deviceId()
        values = {
            "desired_state": {
                "powered": state
            }
        }

        if brightness is not None:
            values["desired_state"]["brightness"] = brightness

        urlString = baseUrl + "/light_bulbs/%s" % self.deviceId()
        arequest = requests.put(urlString, data=json.dumps(values), headers=headers)
        self._updateStateFromResponse(arequest.json())

        self._last_call = (time.time(), state)

    def __repr__(self):
        return "<Wink Bulb %s %s %s>" % (
            self.name(), self.deviceId(), self.state())


def get_devices(filter, constructor):
    arequestUrl = baseUrl + "/users/me/wink_devices"
    j = requests.get(arequestUrl, headers=headers).json()

    items = j.get('data')

    devices = []
    for item in items:
        id = item.get(filter)
        if (id is not None and item.get("hidden_at") is None):
            devices.append(constructor(item))

    return devices

def get_bulbs():
    return get_devices('light_bulb_id', wink_bulb)

def get_switches():
    return get_devices('binary_switch_id', wink_binary_switch)

def get_sensors():
    return get_devices('sensor_pod_id', wink_sensor_pod)

def is_token_set():
    """ Returns if an auth token has been set. """
    return bool(headers)


def set_bearer_token(token):
    global headers

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {}".format(token)
    }

if __name__ == "__main__":
    sw = get_bulbs()
    lamp = sw[3]
    lamp.setState(False)
