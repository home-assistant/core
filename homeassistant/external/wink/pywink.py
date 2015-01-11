__author__ = 'JOHNMCL'

import json

import requests


baseUrl = "https://winkapi.quirky.com"

object_type = "light_bulb"
object_type_plural = "light_bulbs"

bearer_token=""

headers = {}


class wink_binary_switch():
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
    jsonState = {}



    def __init__(self, aJSonObj):
        self.jsonState = aJSonObj
        self.objectprefix = "binary_switches"


    def __str__(self):
        return "%s %s %s" % (self.name(), self.deviceId(), self.state())

    def __repr__(self):
        return "<Wink switch %s %s %s>" % (self.name(), self.deviceId(), self.state())

    def name(self):
        name = self.jsonState.get('name')
        return name or "Unknown Name"

    def state(self):
        state = self.jsonState.get('desired_state').get('powered')
        return state

    def setState(self, state):
        """
        :param state:   a boolean of true (on) or false ('off')
        :return: nothing
        """
        urlString = baseUrl + "/%s/%s" % (self.objectprefix, self.deviceId())
        values = {"desired_state": {"powered": state}}
        urlString = baseUrl + "/%s/%s" % (self.objectprefix, self.deviceId())
        arequest = requests.put(urlString, data=json.dumps(values), headers=headers)
        self._updateStateFromResponse(arequest.json())


    def deviceId(self):
        deviceId = self.jsonState.get('binary_switch_id')
        return deviceId or "Unknown Device ID"

    def updateState(self):
        urlString = baseUrl + "/%s/%s" % (self.objectprefix, self.deviceId())
        arequest = requests.get(urlString, headers=headers)
        self._updateStateFromResponse(arequest.json())

    def _updateStateFromResponse(self, response_json):
        """
        :param response_json: the json obj returned from query
        :return:
        """
        self.jsonState = response_json.get('data')

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
        self.jsonState = ajsonobj
        self.objectprefix = "light_bulbs"

    def __str__(self):
        return "%s %s %s" % (self.name(), self.deviceId(), self.state())

    def __repr__(self):
        return "<Wink Bulb %s %s %s>" % (self.name(), self.deviceId(), self.state())

    def name(self):
        name = self.jsonState.get('name')
        return name or "Unknown Name"

    def state(self):
        state = self.jsonState.get('desired_state').get('powered')
        return state

    def setState(self, state):
        """
        :param state:   a boolean of true (on) or false ('off')
        :return: nothing
        """
        urlString = baseUrl + "/light_bulbs/%s" % self.deviceId()
        values = {"desired_state": {"desired_powered": state, "powered": state}}
        urlString = baseUrl + "/light_bulbs/%s" % self.deviceId()
        arequest = requests.put(urlString, data=json.dumps(values), headers=headers)

        self.updateState()


    def deviceId(self):
        deviceId = self.jsonState.get('light_bulb_id')
        return deviceId or "Unknown Device ID"


def get_bulbs_and_switches():
    arequestUrl = baseUrl + "/users/me/wink_devices"
    j = requests.get(arequestUrl, headers=headers).json()

    items = j.get('data')

    switches = []
    for item in items:
        id = item.get('light_bulb_id')
        if id != None:
            switches.append(wink_bulb(item))
        id = item.get('binary_switch_id')
        if id != None:
            switches.append(wink_binary_switch(item))

    return switches


def get_bulbs():
    arequestUrl = baseUrl + "/users/me/wink_devices"
    j = requests.get(arequestUrl, headers=headers).json()

    items = j.get('data')

    switches = []
    for item in items:
        id = item.get('light_bulb_id')
        if id != None:
            switches.append(wink_bulb(item))

    return switches


def get_switches():
    arequestUrl = baseUrl + "/users/me/wink_devices"
    j = requests.get(arequestUrl, headers=headers).json()

    items = j.get('data')

    switches = []
    for item in items:
        id = item.get('binary_switch_id')
        if id != None:
            switches.append(wink_binary_switch(item))

    return switches

def set_bearer_token(token):
    global headers
    bearer_token=token
    headers={"Content-Type": "application/json", "Authorization": "Bearer {}".format(token)}

if __name__ == "__main__":
    sw = get_bulbs()
    lamp = sw[3]
    lamp.setState(False)
