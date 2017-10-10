"""Hive Integration - Platform."""
import logging
import operator
from datetime import datetime
from datetime import timedelta
from homeassistant.helpers.discovery import load_platform
import requests

HGO = None
_LOGGER = logging.getLogger(__name__)
DOMAIN = 'hive'

HIVE_NODE_UPDATE_INTERVAL_DEFAULT = 120
MINUTES_BETWEEN_LOGONS = 15

NODE_ATTRIBS = {"Header": "HeaderText"}


class HiveDevices:
    """Initiate Hive Devices Class."""

    hub = []
    thermostat = []
    boiler_module = []
    plug = []
    light = []
    sensors = []


class HiveProducts:
    """Initiate Hive Products Class."""

    heating = []
    hotwater = []
    light = []
    plug = []
    sensors = []


class HivePlatformData:
    """Initiate Hive PlatformData Class."""

    min_max_data = {}


class HiveSession:
    """Initiate Hive Session Class."""

    session_id = ""
    session_logon_datetime = datetime(2017, 1, 1, 12, 0, 0)
    username = ""
    password = ""
    postcode = ""
    timezone = ""
    countrycode = ""
    locale = ""
    temperature_unit = ""
    devices = HiveDevices()
    products = HiveProducts()
    platform_data = HivePlatformData()
#    holiday_mode = Hive_HolidayMode()
    update_interval_seconds = HIVE_NODE_UPDATE_INTERVAL_DEFAULT
    last_update = datetime(2017, 1, 1, 12, 0, 0)
    logging = False
    hass = None


class HiveAPIURLS:
    """Initiate Hive API URLS Class."""

    global_login = ""
    base = ""
    weather = ""
    holiday_mode = ""
    devices = ""
    products = ""
    nodes = ""


class HiveAPIHeaders:
    """Initiate Hive API Headers Class."""

    accept_key = ""
    accept_value = ""
    content_type_key = ""
    content_type_value = ""
    session_id_key = ""
    session_id_value = ""


class HiveAPIDetails:
    """Initiate Hive API Details Class."""

    urls = HiveAPIURLS()
    headers = HiveAPIHeaders()
    platform_name = ""


HIVE_API = HiveAPIDetails()
HSC = HiveSession()


def initialise_app():
    """Initialise the base variable values."""
    HIVE_API.platform_name = ""

    HIVE_API.urls.global_login = \
        "https://beekeeper.hivehome.com/1.0/global/login"
    HIVE_API.urls.base = ""
    HIVE_API.urls.weather = "https://weather-prod.bgchprod.info/weather"
    HIVE_API.urls.holiday_mode = "/holiday-mode"
    HIVE_API.urls.devices = "/devices"
    HIVE_API.urls.products = "/products"
    HIVE_API.urls.nodes = "/nodes"

    HIVE_API.headers.accept_key = "Accept"
    HIVE_API.headers.accept_value = "*/*"
    HIVE_API.headers.content_type_key = "content-type"
    HIVE_API.headers.content_type_value = "application/json"
    HIVE_API.headers.session_id_key = "authorization"
    HIVE_API.headers.session_id_value = None


def hive_api_json_call(request_type,
                       request_url,
                       json_string_content,
                       login_request):
    """Call the JSON Hive API and return any returned data."""
    api_headers = {HIVE_API.headers.content_type_key:
                   HIVE_API.headers.content_type_value,
                   HIVE_API.headers.accept_key:
                   HIVE_API.headers.accept_value,
                   HIVE_API.headers.session_id_key:
                   HIVE_API.headers.session_id_value}

    json_return = {}
    full_request_url = ""

    if login_request:
        full_request_url = request_url
    else:
        full_request_url = HIVE_API.urls.base + request_url

    json_call_try_finished = False
    try:
        if request_type == "POST":
            json_response = requests.post(full_request_url,
                                          data=json_string_content,
                                          headers=api_headers)
        elif request_type == "GET":
            json_response = requests.get(full_request_url,
                                         data=json_string_content,
                                         headers=api_headers)
        elif request_type == "PUT":
            json_response = requests.put(full_request_url,
                                         data=json_string_content,
                                         headers=api_headers)
        else:
            _LOGGER.error("Unknown JSON API call RequestType : %s",
                          request_type)

        json_call_try_finished = True
    except (IOError, RuntimeError, ZeroDivisionError):
        json_call_try_finished = False
    finally:
        if not json_call_try_finished:
            json_return['original'] = "No response to JSON Hive API request"
            json_return['parsed'] = "No response to JSON Hive API request"

    if json_call_try_finished:
        parse_json_try_finished = False
        try:
            json_return['original'] = json_response
            json_return['parsed'] = json_response.json()

            parse_json_try_finished = True
        except (IOError, RuntimeError, ZeroDivisionError):
            parse_json_try_finished = False
        finally:
            if not parse_json_try_finished:
                json_return['original'] = "Error parsing JSON data"
                json_return['parsed'] = "Error parsing JSON data"

    return json_return


def hive_api_logon():
    """Log in to the Hive API and get the Session ID."""
    login_details_found = True
    HSC.session_id = None

    try_finished = False
    try:
        api_resp_d = {}
        api_resp_p = None

        json_string_content = '{"username": "' \
                              + HSC.username \
                              + '","password": "' \
                              + HSC.password + '"}'

        api_resp_d = hive_api_json_call("POST",
                                        HIVE_API.urls.global_login,
                                        json_string_content,
                                        True)

        api_resp_p = api_resp_d['parsed']

        if ('token' in api_resp_p and
                'user' in api_resp_p and
                'platform' in api_resp_p):
            HIVE_API.headers.session_id_value = api_resp_p["token"]
            HSC.session_id = HIVE_API.headers.session_id_value
            HSC.session_logon_datetime = datetime.now()

            if 'endpoint' in api_resp_p['platform']:
                HIVE_API.urls.base = api_resp_p['platform']['endpoint']
            else:
                login_details_found = False

            if 'name' in api_resp_p['platform']:
                HIVE_API.platform_name = api_resp_p['platform']['name']
            else:
                login_details_found = False

            if 'locale' in api_resp_p['user']:
                HSC.locale = api_resp_p['user']['locale']
            else:
                login_details_found = False

            if 'countryCode' in api_resp_p['user']:
                HSC.countrycode = api_resp_p['user']['countryCode']
            else:
                login_details_found = False

            if 'timezone' in api_resp_p['user']:
                HSC.timezone = api_resp_p['user']['timezone']
            else:
                login_details_found = False

            if 'postcode' in api_resp_p['user']:
                HSC.postcode = api_resp_p['user']['postcode']
            else:
                login_details_found = False

            if 'temperatureUnit' in api_resp_p['user']:
                HSC.temperature_unit = api_resp_p['user']['temperatureUnit']
            else:
                login_details_found = False
        else:
            login_details_found = False

        try_finished = True
    except (IOError, RuntimeError, ZeroDivisionError):
        try_finished = False
    finally:
        if not try_finished:
            login_details_found = False

    if not login_details_found:
        HSC.session_id = None
        _LOGGER.error("Hive API login failed with error : %s", api_resp_p)


def check_hive_api_logon():
    """Check if currently logged in with a valid Session ID."""
    current_time = datetime.now()
    l_logon_secs = (current_time - HSC.session_logon_datetime).total_seconds()
    l_logon_mins = int(round(l_logon_secs / 60))

    if l_logon_mins >= MINUTES_BETWEEN_LOGONS or HSC.session_id is None:
        hive_api_logon()


def fire_bus_event(node_id, device_type):
    """Fire off an event if some data has changed."""
    fire_events = True
    if fire_events:
        HSC.hass.bus.fire('Event_Hive_NewNodeData', {device_type: node_id})


def hive_api_get_nodes_rl(node_id, device_type):
    """Get latest data for Hive nodes - rate limiting."""
    nodes_updated = False
    current_time = datetime.now()
    last_update_secs = (current_time - HSC.last_update).total_seconds()
    if last_update_secs >= HSC.update_interval_seconds:
        HSC.last_update = current_time
        nodes_updated = hive_api_get_nodes(node_id, device_type)
    return nodes_updated


def hive_api_get_nodes_nl():
    """Get latest data for Hive nodes - not rate limiting."""
    hive_api_get_nodes("NoID", "NoDeviceType")


def hive_api_get_nodes(node_id, device_type):
    """Get latest data for Hive nodes."""
    get_nodes_successful = True

    check_hive_api_logon()

    # pylint: disable=too-many-nested-blocks
    if HSC.session_id is not None:
        tmp_devices_hub = []
        tmp_devices_thermostat = []
        tmp_devices_boiler_module = []
        tmp_devices_plug = []
        tmp_devices_light = []
        tmp_devices_sensors = []

        tmp_products_heating = []
        tmp_products_hotwater = []
        tmp_products_light = []
        tmp_products_plug = []
        tmp_products_sensors = []

        try_finished = False
        try:
            api_resp_d = {}
            api_resp_p = None
            api_resp_d = hive_api_json_call("GET",
                                            HIVE_API.urls.devices,
                                            "",
                                            False)

            api_resp_p = api_resp_d['parsed']

            for a_device in api_resp_p:
                if "type" in a_device:
                    if a_device["type"] == "hub":
                        tmp_devices_hub.append(a_device)
                    if a_device["type"] == "thermostatui":
                        tmp_devices_thermostat.append(a_device)
                    if a_device["type"] == "boilermodule":
                        tmp_devices_boiler_module.append(a_device)
                    if a_device["type"] == "activeplug":
                        tmp_devices_plug.append(a_device)
                    if (a_device["type"] == "warmwhitelight" or
                            a_device["type"] == "tuneablelight" or
                            a_device["type"] == "colourtuneablelight"):
                        tmp_devices_light.append(a_device)
                    if (a_device["type"] == "motionsensor" or
                            a_device["type"] == "contactsensor"):
                        tmp_devices_sensors.append(a_device)

            try_finished = True
        except (IOError, RuntimeError, ZeroDivisionError):
            try_finished = False
        finally:
            if not try_finished:
                _LOGGER.error("Error parsing Hive Devices")

        try_finished = False
        try:
            api_resp_d = {}
            api_resp_p = None
            api_resp_d = hive_api_json_call("GET",
                                            HIVE_API.urls.products,
                                            "",
                                            False)

            api_resp_p = api_resp_d['parsed']

            for a_product in api_resp_p:
                if "type" in a_product:
                    if a_product["type"] == "heating":
                        tmp_products_heating.append(a_product)
                    if a_product["type"] == "hotwater":
                        tmp_products_hotwater.append(a_product)
                    if a_product["type"] == "activeplug":
                        tmp_products_plug.append(a_product)
                    if (a_product["type"] == "warmwhitelight" or
                            a_product["type"] == "tuneablelight" or
                            a_product["type"] == "colourtuneablelight"):
                        tmp_products_light.append(a_product)
                    if (a_product["type"] == "motionsensor" or
                            a_product["type"] == "contactsensor"):
                        tmp_products_sensors.append(a_product)
            try_finished = True
        except (IOError, RuntimeError, ZeroDivisionError):
            try_finished = False
        finally:
            if not try_finished:
                _LOGGER.error("Error parsing Hive Products")

        try_finished = False
        try:
            if len(tmp_devices_hub) > 0:
                HSC.devices.hub = tmp_devices_hub
            if len(tmp_devices_thermostat) > 0:
                HSC.devices.thermostat = tmp_devices_thermostat
            if len(tmp_devices_boiler_module) > 0:
                HSC.devices.boiler_module = tmp_devices_boiler_module
            if len(tmp_devices_plug) > 0:
                HSC.devices.plug = tmp_devices_plug
            if len(tmp_devices_light) > 0:
                HSC.devices.light = tmp_devices_light
            if len(tmp_devices_sensors) > 0:
                HSC.devices.sensors = tmp_devices_sensors

            if len(tmp_products_heating) > 0:
                HSC.products.heating = tmp_products_heating
            if len(tmp_products_hotwater) > 0:
                HSC.products.hotwater = tmp_products_hotwater
            if len(tmp_products_plug) > 0:
                HSC.products.plug = tmp_products_plug
            if len(tmp_products_light) > 0:
                HSC.products.light = tmp_products_light
            if len(tmp_products_sensors) > 0:
                HSC.products.sensors = tmp_products_sensors

            try_finished = True
        except (IOError, RuntimeError, ZeroDivisionError):
            try_finished = False
        finally:
            if not try_finished:
                get_nodes_successful = False
                _LOGGER.error("Error adding discovered Products / Devices")
    else:
        get_nodes_successful = False
        _LOGGER.error("No Session ID")

    if get_nodes_successful:
        fire_bus_event(node_id, device_type)

    return get_nodes_successful


def p_get_heating_min_temp(node_id, device_type):
    """Get heating minimum target temperature."""
    heating_min_temp_default = 5
    heating_min_temp_return = 0
    heating_min_temp_tmp = 0
    heating_min_temp_found = False

    heating_min_temp_tmp = heating_min_temp_default

    current_node_attribute = "Heating_Min_Temperature_" + node_id

    if heating_min_temp_found:
        NODE_ATTRIBS[current_node_attribute] = heating_min_temp_tmp
        heating_min_temp_return = heating_min_temp_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            heating_min_temp_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            heating_min_temp_return = heating_min_temp_default

    return heating_min_temp_return


def p_get_heating_max_temp(node_id, device_type):
    """Get heating maximum target temperature."""
    heating_max_temp_default = 32
    heating_max_temp_return = 0
    heating_max_temp_tmp = 0
    heating_max_temp_found = False

    heating_max_temp_tmp = heating_max_temp_default

    current_node_attribute = "Heating_Max_Temperature_" + node_id

    if heating_max_temp_found:
        NODE_ATTRIBS[current_node_attribute] = heating_max_temp_tmp
        heating_max_temp_return = heating_max_temp_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            heating_max_temp_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            heating_max_temp_return = heating_max_temp_default

    return heating_max_temp_return


def p_get_heating_current_temp(node_id, device_type):
    """Get heating current temperature."""
    node_index = -1

    current_temp_return = 0
    current_temp_tmp = 0
    current_temp_found = False

    current_node_attribute = "Heating_CurrentTemp_" + node_id

    if len(HSC.products.heating) > 0:
        for current_node_index in range(0, len(HSC.products.heating)):
            if "id" in HSC.products.heating[current_node_index]:
                if HSC.products.heating[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if "props" in HSC.products.heating[node_index]:
                if "temperature" in HSC.products.heating[node_index]["props"]:
                    current_temp_tmp = (HSC.products.heating[node_index]
                                        ["props"]["temperature"])
                    current_temp_found = True

    if current_temp_found:
        NODE_ATTRIBS[current_node_attribute] = current_temp_tmp
        current_temp_return = current_temp_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            current_temp_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            current_temp_return = -1000

    if current_temp_return != -1000:
        if node_id in HSC.platform_data.min_max_data:
            if (HSC.platform_data.min_max_data[node_id]['TodayDate'] !=
                    datetime.date(datetime.now())):
                HSC.platform_data.min_max_data[node_id]['TodayMin'] = 1000
                HSC.platform_data.min_max_data[node_id]['TodayMax'] = -1000
                HSC.platform_data.min_max_data[node_id]['TodayDate'] = \
                    datetime.date(datetime.now())

            if (current_temp_return <
                    HSC.platform_data.min_max_data[node_id]['TodayMin']):
                HSC.platform_data.min_max_data[node_id]['TodayMin'] = \
                    current_temp_return

            if (current_temp_return >
                    HSC.platform_data.min_max_data[node_id]['TodayMax']):
                HSC.platform_data.min_max_data[node_id]['TodayMax'] = \
                    current_temp_return

            if (current_temp_return <
                    HSC.platform_data.min_max_data[node_id]['RestartMin']):
                HSC.platform_data.min_max_data[node_id]['RestartMin'] = \
                    current_temp_return

            if current_temp_return > \
                    HSC.platform_data.min_max_data[node_id]['RestartMax']:
                HSC.platform_data.min_max_data[node_id]['RestartMax'] = \
                    current_temp_return
        else:
            current_node_max_min_data = {}
            current_node_max_min_data['TodayMin'] = current_temp_return
            current_node_max_min_data['TodayMax'] = current_temp_return
            current_node_max_min_data['TodayDate'] = \
                datetime.date(datetime.now())
            current_node_max_min_data['RestartMin'] = current_temp_return
            current_node_max_min_data['RestartMax'] = current_temp_return
            HSC.platform_data.min_max_data[node_id] = \
                current_node_max_min_data

    else:
        current_temp_return = 0

    return current_temp_return


def p_get_heating_current_temp_sa(node_id, device_type):
    """Get heating current temperature state attributes."""
    state_attributes = {}
    temperature_current = 0
    temperature_target = 0
    temperature_difference = 0

    if node_id in HSC.platform_data.min_max_data:
        state_attributes.update({"Today Min / Max":
                                 str(HSC.platform_data.min_max_data[node_id]
                                     ['TodayMin']) + " °C" + " / "
                                 + str(HSC.platform_data.min_max_data[node_id]
                                       ['TodayMax']) + " °C"})

        state_attributes.update({"Restart Min / Max":
                                 str(HSC.platform_data.min_max_data[node_id]
                                     ['RestartMin']) + " °C" + " / "
                                 + str(HSC.platform_data.min_max_data[node_id]
                                       ['RestartMax']) + " °C"})

    if len(HSC.products.heating) > 0:
        temperature_current = p_get_heating_current_temp(node_id, device_type)
        temperature_target = p_get_heating_target_temp(node_id, device_type)

        if temperature_target > temperature_current:
            temperature_difference = temperature_target - temperature_current

            state_attributes.update({"Current Temperature":
                                     temperature_current})
            state_attributes.update({"Target Temperature":
                                     temperature_target})
            state_attributes.update({"Temperature Difference":
                                     temperature_difference})
# State_Attributes.update({"Time to target": "01:30"})
    return state_attributes


def p_get_heating_target_temp(node_id, device_type):
    """Get heating target temperature."""
    node_index = -1

    heating_target_temp_return = 0
    heating_target_temp_tmp = 0
    heating_target_temp_found = False

    current_node_attribute = "Heating_TargetTemp_" + node_id

    # pylint: disable=too-many-nested-blocks
    if len(HSC.products.heating) > 0:
        for current_node_index in range(0, len(HSC.products.heating)):
            if "id" in HSC.products.heating[current_node_index]:
                if HSC.products.heating[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            heating_mode_current = p_get_heating_mode(node_id, device_type)
            if heating_mode_current == "SCHEDULE":
                if ('props' in HSC.products.heating[node_index] and
                        'scheduleOverride' in
                        HSC.products.heating[node_index]["props"]):
                    if (HSC.products.heating[node_index]
                            ["props"]["scheduleOverride"]):
                        if ("state" in HSC.products.heating[node_index] and
                                "target" in HSC.products.heating[node_index]
                                ["state"]):
                            heating_target_temp_tmp = (HSC.products.heating
                                                       [node_index]["state"]
                                                       ["target"])
                            heating_target_temp_found = True
                    else:
                        snan = (
                            p_get_schedule_now_next_later(
                                HSC.products.heating[node_index]
                                ["state"]["schedule"]))
                        if 'now' in snan:
                            if ('value' in snan["now"] and
                                    'target' in snan["now"]
                                    ["value"]):
                                heating_target_temp_tmp = (snan["now"]
                                                           ["value"]
                                                           ["target"])
                                heating_target_temp_found = True
            else:
                if ("state" in HSC.products.heating[node_index] and "target"
                        in HSC.products.heating[node_index]["state"]):
                    heating_target_temp_tmp = \
                        HSC.products.heating[node_index]["state"]["target"]
                    heating_target_temp_found = True

    if heating_target_temp_found:
        NODE_ATTRIBS[current_node_attribute] = heating_target_temp_tmp
        heating_target_temp_return = heating_target_temp_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            heating_target_temp_return = \
                NODE_ATTRIBS.get(current_node_attribute)
        else:
            heating_target_temp_return = 0

    return heating_target_temp_return


def p_get_heating_target_temp_sa(node_id, device_type):
    """Get heating target temperature state attributes."""
    state_attributes = {}

    return state_attributes


def p_get_heating_state(node_id, device_type):
    """Get heating current state."""
    heating_state_return = "OFF"
    heating_state_tmp = "OFF"
    heating_state_found = False

    current_node_attribute = "Heating_State_" + node_id

    if len(HSC.products.heating) > 0:
        temperature_current = p_get_heating_current_temp(node_id, device_type)
        temperature_target = p_get_heating_target_temp(node_id, device_type)
        heating_boost = p_get_heating_boost(node_id, device_type)
        heating_mode = p_get_heating_mode(node_id, device_type)

        if (heating_mode == "SCHEDULE" or
                heating_mode == "MANUAL" or
                heating_boost == "ON"):
            if temperature_current < temperature_target:
                heating_state_tmp = "ON"
                heating_state_found = True
            else:
                heating_state_tmp = "OFF"
                heating_state_found = True
        else:
            heating_state_tmp = "OFF"
            heating_state_found = True

    if heating_state_found:
        NODE_ATTRIBS[current_node_attribute] = heating_state_tmp
        heating_state_return = heating_state_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            heating_state_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            heating_state_return = "UNKNOWN"

    return heating_state_return


def p_get_heating_state_sa(node_id, device_type):
    """Get heating current state, state attributes."""
    node_index = -1
    state_attributes = {}

    heating_mode_current = p_get_heating_mode(node_id, device_type)

    if len(HSC.products.heating) > 0:
        for current_node_index in range(0, len(HSC.products.heating)):
            if "id" in HSC.products.heating[current_node_index]:
                if HSC.products.heating[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

    if heating_mode_current == "SCHEDULE":
        snan = (p_get_schedule_now_next_later(HSC.products.heating
                                              [node_index]["state"]
                                              ["schedule"]))
        if 'now' in snan:
            if ('value' in snan["now"] and
                    'start' in snan["now"] and
                    'Start_DateTime' in snan["now"] and
                    'End_DateTime' in snan["now"] and
                    'target' in snan["now"]["value"]):
                now_target = str(snan["now"]["value"]["target"]) + " °C"
                now_start = snan["now"]["Start_DateTime"].strftime("%H:%M")
                now_end = snan["now"]["End_DateTime"].strftime("%H:%M")

                sa_string = (now_target
                             + " : "
                             + now_start
                             + " - "
                             + now_end)
                state_attributes.update({"Now": sa_string})

        if 'next' in snan:
            if ('value' in snan["next"] and
                    'start' in snan["next"] and
                    'Start_DateTime' in snan["next"] and
                    'End_DateTime' in snan["next"] and
                    'target' in snan["next"]["value"]):
                next_target = str(snan["next"]["value"]["target"]) + " °C"
                next_start = snan["next"]["Start_DateTime"].strftime("%H:%M")
                next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                sa_string = (next_target
                             + " : "
                             + next_start
                             + " - "
                             + next_end)
                state_attributes.update({"Next": sa_string})

        if 'later' in snan:
            if ('value' in snan["later"] and
                    'start' in snan["later"] and
                    'Start_DateTime' in snan["later"] and
                    'End_DateTime' in snan["later"] and
                    'target' in snan["later"]["value"]):
                later_target = str(snan["later"]["value"]["target"]) + " °C"
                later_start = snan["later"]["Start_DateTime"].strftime("%H:%M")
                later_end = snan["later"]["End_DateTime"].strftime("%H:%M")

                sa_string = (later_target
                             + " : "
                             + later_start
                             + " - "
                             + later_end)
                state_attributes.update({"Later": sa_string})
    else:
        state_attributes.update({"Schedule not active": ""})

    return state_attributes


def p_get_heating_mode(node_id, device_type):
    """Get heating current mode."""
    node_index = -1

    mode_return = "UNKNOWN"
    mode_tmp = "UNKNOWN"
    mode_found = False

    current_node_attribute = "Heating_Mode_" + node_id

    if len(HSC.products.heating) > 0:
        for current_node_index in range(0, len(HSC.products.heating)):
            if "id" in HSC.products.heating[current_node_index]:
                if HSC.products.heating[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in HSC.products.heating[node_index] and
                    "mode" in HSC.products.heating[node_index]["state"]):
                mode_tmp = HSC.products.heating[node_index]["state"]["mode"]
                if mode_tmp == "BOOST":
                    if ("props" in HSC.products.heating[node_index] and
                            "previous" in
                            HSC.products.heating[node_index]["props"] and
                            "mode" in
                            HSC.products.heating[node_index]
                            ["props"]["previous"]):
                        mode_tmp = (HSC.products.heating[node_index]
                                    ["props"]["previous"]["mode"])
                mode_found = True

    if mode_found:
        NODE_ATTRIBS[current_node_attribute] = mode_tmp
        mode_return = mode_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            mode_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            mode_return = "UNKNOWN"
            _LOGGER.error("Heating Mode not found")

    return mode_return


def p_get_heating_mode_sa(node_id, device_type):
    """Get heating current mode state attributes."""
    state_attributes = p_get_heating_state_sa(node_id, device_type)

    return state_attributes


def p_get_heating_operation_modes(node_id, device_type):
    """Get heating list of possible modes."""
    hive_heating_operation_list = ["SCHEDULE", "MANUAL", "OFF"]
    return hive_heating_operation_list


def p_get_heating_boost(node_id, device_type):
    """Get heating boost current status."""
    node_index = -1

    heating_boost_return = "UNKNOWN"
    heating_boost_tmp = "UNKNOWN"
    heating_boost_found = False

    current_node_attribute = "Heating_Boost_" + node_id

    if len(HSC.products.heating) > 0:
        for current_node_index in range(0, len(HSC.products.heating)):
            if "id" in HSC.products.heating[current_node_index]:
                if HSC.products.heating[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in HSC.products.heating[node_index] and
                    "boost" in HSC.products.heating[node_index]["state"]):
                heating_boost_tmp = (HSC.products.heating[node_index]
                                     ["state"]["boost"])
                if heating_boost_tmp is None:
                    heating_boost_tmp = "OFF"
                else:
                    heating_boost_tmp = "ON"
                heating_boost_found = True

    if heating_boost_found:
        NODE_ATTRIBS[current_node_attribute] = heating_boost_tmp
        heating_boost_return = heating_boost_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            heating_boost_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            heating_boost_return = "UNKNOWN"
            _LOGGER.error("Heating Boost not found")

    return heating_boost_return


def p_get_heating_boost_sa(node_id, device_type):
    """Get heating boost current status state attributes."""
    state_attributes = {}

    if p_get_heating_boost(node_id, device_type) == "ON":
        node_index = -1

        heating_boost_tmp = "UNKNOWN"
        heating_boost_found = False

        if len(HSC.products.heating) > 0:
            for current_node_index in range(0, len(HSC.products.heating)):
                if "id" in HSC.products.heating[current_node_index]:
                    if (HSC.products.heating[current_node_index]
                            ["id"] == node_id):
                        node_index = current_node_index
                        break

            if node_index != -1:
                if ("state" in HSC.products.heating[node_index] and
                        "boost" in HSC.products.heating[node_index]["state"]):
                    heating_boost_tmp = (HSC.products.heating[node_index]
                                         ["state"]["boost"])
                    heating_boost_found = True

        if heating_boost_found:
            state_attributes.update({"Boost ends in":
                                     (str(heating_boost_tmp) + " minutes")})

    return state_attributes


def p_get_hotwater_mode(node_id, device_type):
    """Get hot water current mode."""
    node_index = -1

    hotwater_mode_return = "UNKNOWN"
    hotwater_mode_tmp = "UNKNOWN"
    hotwater_mode_found = False

    current_node_attribute = "HotWater_Mode_" + node_id

    if len(HSC.products.hotwater) > 0:
        for current_node_index in range(0, len(HSC.products.hotwater)):
            if "id" in HSC.products.hotwater[current_node_index]:
                if HSC.products.hotwater[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in HSC.products.hotwater[node_index] and
                    "mode" in HSC.products.hotwater[node_index]["state"]):
                hotwater_mode_tmp = (HSC.products.hotwater[node_index]
                                     ["state"]["mode"])
                if hotwater_mode_tmp == "BOOST":
                    if ("props" in HSC.products.hotwater[node_index] and
                            "previous" in
                            HSC.products.hotwater[node_index]["props"] and
                            "mode" in
                            HSC.products.hotwater[node_index]
                            ["props"]["previous"]):
                        hotwater_mode_tmp = (HSC.products.hotwater[node_index]
                                             ["props"]["previous"]["mode"])
                elif hotwater_mode_tmp == "MANUAL":
                    hotwater_mode_tmp = "ON"
                hotwater_mode_found = True

    if hotwater_mode_found:
        NODE_ATTRIBS[current_node_attribute] = hotwater_mode_tmp
        hotwater_mode_return = hotwater_mode_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            hotwater_mode_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            hotwater_mode_return = "UNKNOWN"
            _LOGGER.error("HotWater Mode not found")

    return hotwater_mode_return


def p_get_hotwater_mode_sa(node_id, device_type):
    """Get hot water current mode state attributes."""
    state_attributes = p_get_hotwater_state_sa(node_id, device_type)

    return state_attributes


def p_get_hotwater_operation_modes(node_id, device_type):
    """Get heating list of possible modes."""
    hive_hotwater_operation_list = ["SCHEDULE", "ON", "OFF"]
    return hive_hotwater_operation_list


def p_get_hotwater_boost(node_id, device_type):
    """Get hot water current boost status."""
    node_index = -1

    hotwater_boost_return = "UNKNOWN"
    hotwater_boost_tmp = "UNKNOWN"
    hotwater_boost_found = False

    current_node_attribute = "HotWater_Boost_" + node_id

    if len(HSC.products.hotwater) > 0:
        for current_node_index in range(0, len(HSC.products.hotwater)):
            if "id" in HSC.products.hotwater[current_node_index]:
                if HSC.products.hotwater[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in HSC.products.hotwater[node_index] and
                    "boost" in HSC.products.hotwater[node_index]["state"]):
                hotwater_boost_tmp = (HSC.products.hotwater[node_index]
                                      ["state"]["boost"])
                if hotwater_boost_tmp is None:
                    hotwater_boost_tmp = "OFF"
                else:
                    hotwater_boost_tmp = "ON"
                hotwater_boost_found = True

    if hotwater_boost_found:
        NODE_ATTRIBS[current_node_attribute] = hotwater_boost_tmp
        hotwater_boost_return = hotwater_boost_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            hotwater_boost_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            hotwater_boost_return = "UNKNOWN"
            _LOGGER.error("HotWater Boost not found")

    return hotwater_boost_return


def p_get_hotwater_boost_sa(node_id, device_type):
    """Get hot water current boost status state attributes."""
    state_attributes = {}

    if p_get_hotwater_boost(node_id, device_type) == "ON":
        node_index = -1

        hotwater_boost_tmp = "UNKNOWN"
        hotwater_boost_found = False

        if len(HSC.products.hotwater) > 0:
            for current_node_index in range(0, len(HSC.products.hotwater)):
                if "id" in HSC.products.hotwater[current_node_index]:
                    if (HSC.products.hotwater[current_node_index]["id"]
                            == node_id):
                        node_index = current_node_index
                        break

            if node_index != -1:
                if ("state" in
                        HSC.products.hotwater[node_index] and
                        "boost" in
                        HSC.products.hotwater[node_index]["state"]):
                    hotwater_boost_tmp = (HSC.products.hotwater[node_index]
                                          ["state"]["boost"])
                    hotwater_boost_found = True

        if hotwater_boost_found:
            state_attributes.update({"Boost ends in":
                                     (str(hotwater_boost_tmp) + " minutes")})

    return state_attributes


def p_get_hotwater_state(node_id, device_type):
    """Get hot water current state."""
    node_index = -1

    state_return = "OFF"
    state_tmp = "OFF"
    state_found = False
    mode_current = p_get_hotwater_mode(node_id, device_type)

    current_node_attribute = "HotWater_State_" + node_id

    # pylint: disable=too-many-nested-blocks
    if len(HSC.products.hotwater) > 0:
        for current_node_index in range(0, len(HSC.products.hotwater)):
            if "id" in HSC.products.hotwater[current_node_index]:
                if HSC.products.hotwater[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in HSC.products.hotwater[node_index] and
                    "status" in HSC.products.hotwater[node_index]["state"]):
                state_tmp = (HSC.products.hotwater[node_index]
                             ["state"]["status"])
                if state_tmp is None:
                    state_tmp = "OFF"
                else:
                    if mode_current == "SCHEDULE":
                        if p_get_hotwater_boost(node_id, device_type) == "ON":
                            state_tmp = "ON"
                            state_found = True
                        else:
                            if ("state" in
                                    HSC.products.hotwater[node_index] and
                                    "schedule" in
                                    HSC.products.hotwater[node_index]
                                    ["state"]):
                                snan = p_get_schedule_now_next_later(
                                    HSC.products.hotwater[node_index]
                                    ["state"]["schedule"])
                                if 'now' in snan:
                                    if ('value' in snan["now"] and
                                            'status' in snan["now"]["value"]):
                                        state_tmp = (snan["now"]["value"]
                                                     ["status"])
                                        state_found = True
                    else:
                        state_found = True

    if state_found:
        NODE_ATTRIBS[current_node_attribute] = state_tmp
        state_return = state_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            state_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            state_return = "UNKNOWN"

    return state_return


def p_get_hotwater_state_sa(node_id, device_type):
    """Get hot water current status state attributes."""
    node_index = -1
    state_attributes = {}

    hotwater_mode_current = p_get_hotwater_mode(node_id, device_type)

    if len(HSC.products.hotwater) > 0:
        for current_node_index in range(0, len(HSC.products.hotwater)):
            if "id" in HSC.products.hotwater[current_node_index]:
                if HSC.products.hotwater[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break
    if hotwater_mode_current == "SCHEDULE":
        snan = p_get_schedule_now_next_later(
            HSC.products.hotwater[node_index]["state"]["schedule"])
        if 'now' in snan:
            if ('value' in snan["now"] and
                    'start' in snan["now"] and
                    'Start_DateTime' in snan["now"] and
                    'End_DateTime' in snan["now"] and
                    'status' in snan["now"]["value"]):
                now_status = snan["now"]["value"]["status"]
                now_start = snan["now"]["Start_DateTime"].strftime("%H:%M")
                now_end = snan["now"]["End_DateTime"].strftime("%H:%M")

                sa_string = (now_status
                             + " : "
                             + now_start
                             + " - "
                             + now_end)
                state_attributes.update({"Now": sa_string})

        if 'next' in snan:
            if ('value' in snan["next"] and
                    'start' in snan["next"] and
                    'Start_DateTime' in snan["next"] and
                    'End_DateTime' in snan["next"] and
                    'status' in snan["next"]["value"]):
                next_status = snan["next"]["value"]["status"]
                next_start = snan["next"]["Start_DateTime"].strftime("%H:%M")
                next_end = snan["next"]["End_DateTime"].strftime("%H:%M")

                sa_string = (next_status
                             + " : "
                             + next_start
                             + " - "
                             + next_end)
                state_attributes.update({"Next": sa_string})
        if 'later' in snan:
            if ('value' in snan["later"] and
                    'start' in snan["later"] and
                    'Start_DateTime' in snan["later"] and
                    'End_DateTime' in snan["later"] and
                    'status' in snan["later"]["value"]):
                later_status = snan["later"]["value"]["status"]
                later_start = (snan["later"]
                               ["Start_DateTime"].strftime("%H:%M"))
                later_end = snan["later"]["End_DateTime"].strftime("%H:%M")

                sa_string = (later_status
                             + " : "
                             + later_start
                             + " - "
                             + later_end)
                state_attributes.update({"Later": sa_string})
    else:
        state_attributes.update({"Schedule not active": ""})

    return state_attributes


def p_get_device_battery_level(node_id,
                               node_name,
                               device_type,
                               node_device_type):
    """Get device battery level."""
    node_index = -1

    battery_level_return = 0
    battery_level_tmp = 0
    battery_level_found = False
    all_devices = HSC.devices.thermostat + HSC.devices.sensors

    current_node_attribute = "BatteryLevel_" + node_id

    if len(HSC.devices.thermostat) > 0 or len(HSC.devices.sensors) > 0:
        for current_node_index in range(0, len(all_devices)):
            if "id" in all_devices[current_node_index]:
                if all_devices[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("props" in all_devices[node_index] and
                    "battery" in all_devices[node_index]["props"]):
                battery_level_tmp = (all_devices[node_index]
                                     ["props"]["battery"])
                battery_level_found = True

    if battery_level_found:
        NODE_ATTRIBS[current_node_attribute] = battery_level_tmp
        battery_level_return = battery_level_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            battery_level_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            battery_level_return = 0
    if HSC.logging:
        _LOGGER.warning("Battery level is %s", battery_level_return)
    return battery_level_return


def p_get_light_state(node_id, device_type, node_name):
    """Get light current state."""
    node_index = -1

    light_state_return = "UNKNOWN"
    light_state_tmp = "UNKNOWN"
    light_state_found = False

    current_node_attribute = "Light_State_" + node_id

    if len(HSC.products.light) > 0:
        for current_node_index in range(0, len(HSC.products.light)):
            if "id" in HSC.products.light[current_node_index]:
                if HSC.products.light[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in HSC.products.light[node_index] and "status" in
                    HSC.products.light[node_index]["state"]):
                light_state_tmp = (HSC.products.light[node_index]
                                   ["state"]["status"])
                light_state_found = True

    if light_state_found:
        NODE_ATTRIBS[current_node_attribute] = light_state_tmp
        light_state_return = light_state_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            light_state_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            light_state_return = "UNKNOWN"

    light_state_return_b = False

    if HSC.logging:
        _LOGGER.warning("State is %s", light_state_return)
    if light_state_return == "ON":
        light_state_return_b = True

    return light_state_return_b


def p_get_light_brightness(node_id, device_type, node_name):
    """Get light current brightness."""
    node_index = -1

    tmp_brightness_return = 0
    light_brightness_return = 0
    light_brightness_tmp = 0
    light_brightness_found = False

    current_node_attribute = "Light_Brightness_" + node_id

    if len(HSC.products.light) > 0:
        for current_node_index in range(0, len(HSC.products.light)):
            if "id" in HSC.products.light[current_node_index]:
                if HSC.products.light[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in HSC.products.light[node_index] and "brightness" in
                    HSC.products.light[node_index]["state"]):
                light_brightness_tmp = (HSC.products.light[node_index]
                                        ["state"]["brightness"])
                light_brightness_found = True

    if light_brightness_found:
        NODE_ATTRIBS[current_node_attribute] = light_brightness_tmp
        tmp_brightness_return = light_brightness_tmp
        light_brightness_return = ((tmp_brightness_return / 100) * 255)
    else:
        if current_node_attribute in NODE_ATTRIBS:
            tmp_brightness_return = NODE_ATTRIBS.get(current_node_attribute)
            light_brightness_return = ((tmp_brightness_return / 100) * 255)
        else:
            light_brightness_return = 0

    if HSC.logging:
        _LOGGER.warning("Brightness is %s percent", tmp_brightness_return)
    return light_brightness_return


def p_get_light_min_color_temp(node_id, device_type, node_name):
    """Get light minimum colour temperature."""
    node_index = -1

    light_min_color_temp_tmp = 0
    light_min_color_temp_return = 0
    light_min_color_temp_found = False

    node_attrib = "Light_Min_Color_Temp_" + node_id

    if len(HSC.products.light) > 0:
        for current_node_index in range(0, len(HSC.products.light)):
            if "id" in HSC.products.light[current_node_index]:
                if HSC.products.light[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("props" in HSC.products.light[node_index] and
                    "colourTemperature" in
                    HSC.products.light[node_index]["props"] and "max" in
                    HSC.products.light[node_index]
                    ["props"]["colourTemperature"]):
                light_min_color_temp_tmp = (HSC.products.light[node_index]
                                            ["props"]
                                            ["colourTemperature"]["max"])
                light_min_color_temp_found = True

    if light_min_color_temp_found:
        NODE_ATTRIBS[node_attrib] = light_min_color_temp_tmp
        light_min_color_temp_return = round((1 / light_min_color_temp_tmp)
                                            * 1000000)
    else:
        if node_attrib in NODE_ATTRIBS:
            light_min_color_temp_return = (NODE_ATTRIBS.get(node_attrib))
        else:
            light_min_color_temp_return = 0

    return light_min_color_temp_return


def p_get_light_max_color_temp(node_id, device_type, node_name):
    """Get light maximum colour temperature."""
    node_index = -1

    light_max_color_temp_tmp = 0
    light_max_color_temp_return = 0
    light_max_color_temp_found = False

    node_attrib = "Light_Max_Color_Temp_" + node_id

    if len(HSC.products.light) > 0:
        for current_node_index in range(0, len(HSC.products.light)):
            if "id" in HSC.products.light[current_node_index]:
                if HSC.products.light[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("props" in HSC.products.light[node_index] and
                    "colourTemperature" in
                    HSC.products.light[node_index]["props"] and
                    "min" in
                    HSC.products.light[node_index]["props"]
                    ["colourTemperature"]):
                light_max_color_temp_tmp = (HSC.products.light[node_index]
                                            ["props"]["colourTemperature"]
                                            ["min"])
                light_max_color_temp_found = True

    if light_max_color_temp_found:
        NODE_ATTRIBS[node_attrib] = light_max_color_temp_tmp
        light_max_color_temp_return = round((1 / light_max_color_temp_tmp)
                                            * 1000000)
    else:
        if node_attrib in NODE_ATTRIBS:
            light_max_color_temp_return = NODE_ATTRIBS.get(node_attrib)
        else:
            light_max_color_temp_return = 0

    return light_max_color_temp_return


def p_get_light_color_temp(node_id, device_type, node_name):
    """Get light current colour temperature."""
    node_index = -1

    light_color_temp_tmp = 0
    light_color_temp_return = 0
    light_color_temp_found = False

    current_node_attribute = "Light_Color_Temp_" + node_id

    if len(HSC.products.light) > 0:
        for current_node_index in range(0, len(HSC.products.light)):
            if "id" in HSC.products.light[current_node_index]:
                if HSC.products.light[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in HSC.products.light[node_index] and
                    "colourTemperature" in
                    HSC.products.light[node_index]["state"]):
                light_color_temp_tmp = (HSC.products.light[node_index]
                                        ["state"]["colourTemperature"])
                light_color_temp_found = True

    if light_color_temp_found:
        NODE_ATTRIBS[current_node_attribute] = light_color_temp_tmp
        light_color_temp_return = round((1 / light_color_temp_tmp) * 1000000)
    else:
        if current_node_attribute in NODE_ATTRIBS:
            light_color_temp_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            light_color_temp_return = 0

    if HSC.logging:
        _LOGGER.warning("Colour temperature is %s", light_color_temp_return)
    return light_color_temp_return


def p_get_smartplug_state(node_id, device_type, node_name):
    """Get smart plug current state."""
    node_index = -1

    smartplug_state_tmp = "UNKNOWN"
    smartplug_state_return = "UNKNOWN"
    smartplug_state_found = False

    current_node_attribute = "Smartplug_State_" + node_id

    if len(HSC.products.plug) > 0:
        for current_node_index in range(0, len(HSC.products.plug)):
            if "id" in HSC.products.plug[current_node_index]:
                if HSC.products.plug[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in HSC.products.plug[node_index] and "status" in
                    HSC.products.plug[node_index]["state"]):
                smartplug_state_tmp = (HSC.products.plug[node_index]
                                       ["state"]["status"])
                smartplug_state_found = True

    if smartplug_state_found:
        NODE_ATTRIBS[current_node_attribute] = smartplug_state_tmp
        smartplug_state_return = smartplug_state_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            smartplug_state_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            smartplug_state_return = "UNKNOWN"

    smartplug_state_return_b = False

    if HSC.logging:
        _LOGGER.warning("State is %s", smartplug_state_return)
    if smartplug_state_return == "ON":
        smartplug_state_return_b = True

    return smartplug_state_return_b


def p_get_smartplug_power_usage(node_id, device_type, node_name):
    """Get smart plug current power usage."""
    node_index = -1

    current_power_tmp = 0
    current_power_return = 0
    current_power_found = False

    current_node_attribute = "Smartplug_Current_Power_" + node_id

    if len(HSC.products.plug) > 0:
        for current_node_index in range(0, len(HSC.products.plug)):
            if "id" in HSC.products.plug[current_node_index]:
                if HSC.products.plug[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("props" in HSC.products.plug[node_index]
                    and "powerConsumption"
                    in HSC.products.plug[node_index]["props"]):
                current_power_tmp = (HSC.products.plug[node_index]
                                     ["props"]["powerConsumption"])
                current_power_found = True

    if current_power_found:
        NODE_ATTRIBS[current_node_attribute] = current_power_tmp
        current_power_return = current_power_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            current_power_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            current_power_return = 0

    if HSC.logging:
        _LOGGER.warning("Power consumption is %s", current_power_return)
    return current_power_return


def p_get_hive_sensor_state(node_id,
                            device_type,
                            node_name,
                            node_device_type):
    """Get sensor current state."""
    node_index = -1

    sensor_state_tmp = ""
    sensor_state_return = ""
    sensor_found = False

    current_node_attribute = "Sensor_State_" + node_id

    if len(HSC.products.sensors) > 0:
        for current_node_index in range(0, len(HSC.products.sensors)):
            if "id" in HSC.products.sensors[current_node_index]:
                if HSC.products.sensors[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if node_device_type == "contactsensor":
                if ("props" in HSC.products.sensors[node_index] and
                        "status" in
                        HSC.products.sensors[node_index]["props"]):
                    sensor_state_tmp = (HSC.products.sensors[node_index]
                                        ["props"]["status"])
                    sensor_found = True
            elif node_device_type == "motionsensor":
                if ("props" in HSC.products.sensors[node_index] and
                        "motion" in HSC.products.sensors[node_index]["props"]
                        and "status" in
                        HSC.products.sensors[node_index]["props"]["motion"]):
                    if (HSC.products.sensors[node_index]
                            ["props"]["motion"]["status"]):
                        sensor_state_tmp = "MOTION"
                        sensor_found = True
                    elif not (HSC.products.sensors[node_index]
                              ["props"]["motion"]["status"]):
                        sensor_state_tmp = "NO MOTION"
                        sensor_found = True
                    else:
                        sensor_state_tmp = "UNKNOWN"
                        sensor_found = True

    if sensor_found:
        NODE_ATTRIBS[current_node_attribute] = sensor_state_tmp
        sensor_state_return = sensor_state_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            sensor_state_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            sensor_state_return = "UNKNOWN"

    if HSC.logging:
        _LOGGER.warning("Sensor state is %s", sensor_state_return)
    return sensor_state_return


def p_get_hive_device_mode(node_id, device_type, node_name, node_device_type):
    """Get device current mode."""
    node_index = -1

    hive_device_mode_tmp = ""
    hive_device_mode_return = ""
    hive_device_mode_found = False
    all_devices = HSC.products.light + HSC.products.plug

    current_node_attribute = "Device_Mode_" + node_id

    if len(HSC.products.light) > 0 or len(HSC.products.plug) > 0:
        for current_node_index in range(0, len(all_devices)):
            if "id" in all_devices[current_node_index]:
                if all_devices[current_node_index]["id"] == node_id:
                    node_index = current_node_index
                    break

        if node_index != -1:
            if ("state" in all_devices[node_index] and
                    "mode" in all_devices[node_index]["state"]):
                hive_device_mode_tmp = (all_devices[node_index]
                                        ["state"]["mode"])
                hive_device_mode_found = True

    if hive_device_mode_found:
        NODE_ATTRIBS[current_node_attribute] = hive_device_mode_tmp
        hive_device_mode_return = hive_device_mode_tmp
    else:
        if current_node_attribute in NODE_ATTRIBS:
            hive_device_mode_return = NODE_ATTRIBS.get(current_node_attribute)
        else:
            hive_device_mode_return = "UNKNOWN"

    if HSC.logging:
        _LOGGER.warning("Device Mode is %s", hive_device_mode_return)
    return hive_device_mode_return


def p_hive_set_temperature(node_id, device_type, new_temperature):
    """Set heating target temperature."""
    check_hive_api_logon()

    set_mode_success = False
    api_resp_d = {}
    api_resp = ""

    if HSC.session_id is not None:
        node_index = -1
        if len(HSC.products.heating) > 0:
            for current_node_index in range(0, len(HSC.products.heating)):
                if "id" in HSC.products.heating[current_node_index]:
                    if (HSC.products.heating[current_node_index]
                            ["id"] == node_id):
                        node_index = current_node_index
                        break

            if node_index != -1:
                if "id" in HSC.products.heating[node_index]:
                    json_string_content = ('{"target":'
                                           + str(new_temperature)
                                           + '}')

                    hive_api_url = (HIVE_API.urls.nodes + "/heating/"
                                    + HSC.products.heating[node_index]["id"])
                    api_resp_d = hive_api_json_call("POST",
                                                    hive_api_url,
                                                    json_string_content,
                                                    False)

                    api_resp = api_resp_d['original']

                    if str(api_resp) == "<Response [200]>":
                        hive_api_get_nodes(node_id, device_type)
                        fire_bus_event(node_id, device_type)
                        set_mode_success = True

    return set_mode_success


def p_hive_set_heating_mode(node_id, device_type, new_mode):
    """Set heating mode."""
    check_hive_api_logon()

    set_mode_success = False
    api_resp_d = {}
    api_resp = ""

    if HSC.session_id is not None:
        node_index = -1
        if len(HSC.products.heating) > 0:
            for current_node_index in range(0, len(HSC.products.heating)):
                if "id" in HSC.products.heating[current_node_index]:
                    if (HSC.products.heating[current_node_index]
                            ["id"] == node_id):
                        node_index = current_node_index
                        break

            if node_index != -1:
                if "id" in HSC.products.heating[node_index]:
                    if new_mode == "SCHEDULE":
                        json_string_content = '{"mode": "SCHEDULE"}'
                    elif new_mode == "MANUAL":
                        json_string_content = '{"mode": "MANUAL"}'
                    elif new_mode == "OFF":
                        json_string_content = '{"mode": "OFF"}'

                    if (new_mode == "SCHEDULE" or
                            new_mode == "MANUAL" or
                            new_mode == "OFF"):
                        hive_api_url = (HIVE_API.urls.nodes
                                        + "/heating/"
                                        + HSC.products.heating[node_index]
                                        ["id"])
                        api_resp_d = hive_api_json_call("POST",
                                                        hive_api_url,
                                                        json_string_content,
                                                        False)

                        api_resp = api_resp_d['original']

                        if str(api_resp) == "<Response [200]>":
                            hive_api_get_nodes(node_id, device_type)
                            fire_bus_event(node_id, device_type)
                            set_mode_success = True

    return set_mode_success


def p_hive_set_hotwater_mode(node_id, device_type, new_mode):
    """Set hot water mode."""
    check_hive_api_logon()

    set_mode_success = False
    api_resp_d = {}
    api_resp = ""

    if HSC.session_id is not None:
        node_index = -1
        if len(HSC.products.hotwater) > 0:
            for current_node_index in range(0, len(HSC.products.hotwater)):
                if "id" in HSC.products.hotwater[current_node_index]:
                    if (HSC.products.hotwater[current_node_index]
                            ["id"] == node_id):
                        node_index = current_node_index
                        break

            if node_index != -1:
                if "id" in HSC.products.hotwater[node_index]:
                    if new_mode == "SCHEDULE":
                        json_string_content = '{"mode": "SCHEDULE"}'
                    elif new_mode == "ON":
                        json_string_content = '{"mode": "MANUAL"}'
                    elif new_mode == "OFF":
                        json_string_content = '{"mode": "OFF"}'

                    if (new_mode == "SCHEDULE" or
                            new_mode == "ON" or
                            new_mode == "OFF"):
                        hive_api_url = (HIVE_API.urls.nodes
                                        + "/hotwater/"
                                        + HSC.products.hotwater[node_index]
                                        ["id"])
                        api_resp_d = hive_api_json_call("POST",
                                                        hive_api_url,
                                                        json_string_content,
                                                        False)

                        api_resp = api_resp_d['original']

                        if str(api_resp) == "<Response [200]>":
                            hive_api_get_nodes(node_id, device_type)
                            fire_bus_event(node_id, device_type)
                            set_mode_success = True

    return set_mode_success


def p_hive_set_light_turn_on(node_id,
                             device_type,
                             node_device_type,
                             node_name,
                             new_brightness,
                             new_color_temp):
    """Set light to turn on."""
    node_index = -1

    check_hive_api_logon()

    set_mode_success = False
    api_resp_d = {}
    api_resp = ""

    if HSC.session_id is not None:
        if len(HSC.products.light) > 0:
            for cni in range(0, len(HSC.products.light)):
                if "id" in HSC.products.light[cni]:
                    if HSC.products.light[cni]["id"] == node_id:
                        node_index = cni
                        break
            if node_index != -1:
                if new_brightness is None and new_color_temp is None:
                    json_string_content = '{"status": "ON"}'
                elif new_brightness is not None and new_color_temp is None:
                    json_string_content = ('{"status": "ON", "brightness": '
                                           + str(new_brightness)
                                           + '}')
                elif new_color_temp is not None and new_brightness is None:
                    json_string_content = ('{"colourTemperature": '
                                           + str(new_color_temp)
                                           + '}')
#                elif NewRGBColor != None and NewColorTemp == None and
#                NewBrightness is None:
#                    JsonStringContent = '{"rgbcolour": ' + NewRGBColour + '}'

                hive_api_url = (HIVE_API.urls.nodes
                                + '/' + node_device_type
                                + '/' + HSC.products.light[node_index]["id"])
                api_resp_d = hive_api_json_call("POST",
                                                hive_api_url,
                                                json_string_content,
                                                False)

                api_resp = api_resp_d['original']

            if str(api_resp) == "<Response [200]>":
                hive_api_get_nodes(node_id, device_type)
                fire_bus_event(node_id, device_type)
                set_mode_success = True

    return set_mode_success


def p_hive_set_light_turn_off(node_id,
                              device_type,
                              node_device_type,
                              node_name):
    """Set light to turn off."""
    node_index = -1

    check_hive_api_logon()

    set_mode_success = False
    api_resp_d = {}
    api_resp = ""

    if HSC.session_id is not None:
        if len(HSC.products.light) > 0:
            for current_node_index in range(0, len(HSC.products.light)):
                if "id" in HSC.products.light[current_node_index]:
                    if (HSC.products.light[current_node_index]
                            ["id"] == node_id):
                        node_index = current_node_index
                        break
            if node_index != -1:
                json_string_content = '{"status": "OFF"}'
                hive_api_url = (HIVE_API.urls.nodes
                                + '/'
                                + node_device_type
                                + '/'
                                + HSC.products.light[node_index]["id"])
                api_resp_d = hive_api_json_call("POST",
                                                hive_api_url,
                                                json_string_content,
                                                False)

                api_resp = api_resp_d['original']

            else:
                _LOGGER.error("Unable to control %s", node_name)

            if str(api_resp) == "<Response [200]>":
                hive_api_get_nodes(node_id, device_type)
                fire_bus_event(node_id, device_type)
                set_mode_success = True

    return set_mode_success


def p_hive_set_smartplug_turn_on(node_id,
                                 device_type,
                                 node_name,
                                 node_device_type):
    """Set smart plug to turn on."""
    node_index = -1

    check_hive_api_logon()

    set_mode_success = False
    api_resp_d = {}
    api_resp = ""

    if HSC.session_id is not None:
        if len(HSC.products.plug) > 0:
            for current_node_index in range(0, len(HSC.products.plug)):
                if "id" in HSC.products.plug[current_node_index]:
                    if HSC.products.plug[current_node_index]["id"] == node_id:
                        node_index = current_node_index
                        break
            if node_index != -1:
                json_string_content = '{"status": "ON"}'
                hive_api_url = (HIVE_API.urls.nodes
                                + '/'
                                + node_device_type
                                + '/'
                                + HSC.products.plug[node_index]["id"])
                api_resp_d = hive_api_json_call("POST",
                                                hive_api_url,
                                                json_string_content,
                                                False)

                api_resp = api_resp_d['original']

            else:
                _LOGGER.error("Unable to control %s", node_name)

            if str(api_resp) == "<Response [200]>":
                hive_api_get_nodes(node_id, device_type)
                fire_bus_event(node_id, device_type)
                set_mode_success = True

    return set_mode_success


def p_hive_set_smartplug_turn_off(node_id,
                                  device_type,
                                  node_name,
                                  node_device_type):
    """Set smart plug to turn off."""
    node_index = -1

    check_hive_api_logon()

    set_mode_success = False
    api_resp_d = {}
    api_resp = ""

    if HSC.session_id is not None:
        if len(HSC.products.plug) > 0:
            for current_node_index in range(0, len(HSC.products.plug)):
                if "id" in HSC.products.plug[current_node_index]:
                    if HSC.products.plug[current_node_index]["id"] == node_id:
                        node_index = current_node_index
                        break
            if node_index != -1:
                json_string_content = '{"status": "OFF"}'
                hive_api_url = (HIVE_API.urls.nodes
                                + '/'
                                + node_device_type
                                + '/'
                                + HSC.products.plug[node_index]["id"])
                api_resp_d = hive_api_json_call("POST",
                                                hive_api_url,
                                                json_string_content,
                                                False)

                api_resp = api_resp_d['original']

            else:
                _LOGGER.error("Unable to control %s", node_name)

            if str(api_resp) == "<Response [200]>":
                hive_api_get_nodes(node_id, device_type)
                fire_bus_event(node_id, device_type)
                set_mode_success = True

    return set_mode_success


def p_minutes_to_time(minutes_to_convert):
    """Convert minutes string to datetime."""
    hours_converted, minutes_converted = divmod(minutes_to_convert, 60)
    converted_time = datetime.strptime(str(hours_converted)
                                       + ":"
                                       + str(minutes_converted),
                                       "%H:%M")
    converted_time_string = converted_time.strftime("%H:%M")
    return converted_time_string


def p_datetime_to_cust_string(datetime_to_convert):
    """Convert datetime to custom string."""
    return_string = ""
    seconds_difference = (datetime.now()
                          - datetime_to_convert).total_seconds()

    if seconds_difference < 60:
        return_string = str(round(seconds_difference)) + " seconds ago"
    elif seconds_difference >= 60 and seconds_difference <= (60 * 60):
        return_string = str(round(seconds_difference / 60)) + " minutes ago"
    elif (seconds_difference > (60 * 60) and
          seconds_difference <= (60 * 60 * 24)):
        return_string = datetime_to_convert.strftime('%H:%M')
    else:
        return_string = datetime_to_convert.strftime('%H:%M %d-%b-%Y')

    return return_string


def p_epoch_to_datetime(epoch_string_milliseconds):
    """Convert epoch time in milliseconds string to datetime in UTC."""
    epoch_string_seconds = epoch_string_milliseconds / 1000
    date_time_utc = datetime.fromtimestamp(epoch_string_seconds)
    return date_time_utc


def p_get_schedule_now_next_later(hive_api_schedule):
    """Get the schedule now, next and later of a given nodes schedule."""
    schedule_now_and_next = {}
    date_time_now = datetime.now()
    date_time_now_day_int = date_time_now.today().weekday()

    days_t = ('monday',
              'tuesday',
              'wednesday',
              'thursday',
              'friday',
              'saturday',
              'sunday')

    days_rolling_list = list(days_t[date_time_now_day_int:] + days_t)[:7]

    full_schedule_list = []

    for day_index in range(0, len(days_rolling_list)):
        current_day_schedule = hive_api_schedule[days_rolling_list[day_index]]
        current_day_schedule_sorted = sorted(current_day_schedule,
                                             key=operator.itemgetter('start'),
                                             reverse=False)

        for current_slot in range(0, len(current_day_schedule_sorted)):
            current_slot_custom = current_day_schedule_sorted[current_slot]

            slot_date = datetime.now() + timedelta(days=day_index)
            slot_time = p_minutes_to_time(current_slot_custom["start"])
            slot_time_date_s = (slot_date.strftime("%d-%m-%Y")
                                + " "
                                + slot_time)
            slot_time_date_dt = datetime.strptime(slot_time_date_s,
                                                  "%d-%m-%Y %H:%M")
            if slot_time_date_dt <= date_time_now:
                slot_time_date_dt = slot_time_date_dt + timedelta(days=7)

            current_slot_custom['Start_DateTime'] = slot_time_date_dt
            full_schedule_list.append(current_slot_custom)

    fsl_sorted = sorted(full_schedule_list,
                        key=operator.itemgetter('Start_DateTime'),
                        reverse=False)

    schedule_now = fsl_sorted[-1]
    schedule_next = fsl_sorted[0]
    schedule_later = fsl_sorted[1]

    schedule_now['Start_DateTime'] = (schedule_now['Start_DateTime']
                                      - timedelta(days=7))

    schedule_now['End_DateTime'] = schedule_next['Start_DateTime']
    schedule_next['End_DateTime'] = schedule_later['Start_DateTime']
    schedule_later['End_DateTime'] = fsl_sorted[2]['Start_DateTime']

    schedule_now_and_next['now'] = schedule_now
    schedule_now_and_next['next'] = schedule_next
    schedule_now_and_next['later'] = schedule_later

    return schedule_now_and_next


def setup(hass, config):
    """Setup the Hive platform."""
    initialise_app()

    HSC.hass = hass

    HSC.username = None
    HSC.password = None

    hive_config = config[DOMAIN]

    if "username" in hive_config and "password" in hive_config:
        HSC.username = config[DOMAIN]['username']
        HSC.password = config[DOMAIN]['password']
    else:
        _LOGGER.error("Missing UserName or Password in config")

    if "minutes_between_updates" in hive_config:
        tmp_mins_between_upds = config[DOMAIN]['minutes_between_updates']
    else:
        tmp_mins_between_upds = 2

    hive_node_update_interval = tmp_mins_between_upds * 60

    if "logging" in hive_config:
        if config[DOMAIN]['logging']:
            HSC.logging = True
            _LOGGER.warning("Logging is Enabled")
        else:
            HSC.logging = False
    else:
        HSC.logging = False

    if HSC.username is None or HSC.password is None:
        _LOGGER.error("Missing UserName or Password in Hive Session details")
    else:
        hive_api_logon()
        if HSC.session_id is not None:
            HSC.update_interval_seconds = hive_node_update_interval
            hive_api_get_nodes_nl()

    config_devices = []

    if "devices" in hive_config:
        config_devices = config[DOMAIN]['devices']

    device_count = 0

    device_list_sensor = []
    device_list_climate = []
    device_list_light = []
    device_list_plug = []

    if len(HSC.products.heating) > 0:
        for product in HSC.products.heating:
            if ("id" in product and
                    "state" in product and
                    "name" in product["state"]):
                node_name = product["state"]["name"]
                if len(HSC.products.heating) == 1:
                    node_name = None

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_heating" in config_devices)):
                    device_count = device_count + 1
                    device_list_climate.append({'HA_DeviceType': 'Heating',
                                                'Hive_NodeID': product["id"],
                                                'Hive_NodeName': node_name})

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_heating_currenttemperature" in config_devices)):
                    device_count = device_count + 1
                    device_list_sensor.append({'HA_DeviceType':
                                               'Heating_CurrentTemperature',
                                               'Hive_NodeID': product["id"],
                                               'Hive_NodeName': node_name})

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_heating_targettemperature" in config_devices)):
                    device_count = device_count + 1
                    device_list_sensor.append({'HA_DeviceType':
                                               'Heating_TargetTemperature',
                                               'Hive_NodeID': product["id"],
                                               'Hive_NodeName': node_name})

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_heating_state" in config_devices)):
                    device_count = device_count + 1
                    device_list_sensor.append({'HA_DeviceType':
                                               'Heating_State',
                                               'Hive_NodeID': product["id"],
                                               'Hive_NodeName': node_name})

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_heating_mode" in config_devices)):
                    device_count = device_count + 1
                    device_list_sensor.append({'HA_DeviceType':
                                               'Heating_Mode',
                                               'Hive_NodeID': product["id"],
                                               'Hive_NodeName': node_name})

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_heating_boost" in config_devices)):
                    device_count = device_count + 1
                    device_list_sensor.append({'HA_DeviceType':
                                               'Heating_Boost',
                                               'Hive_NodeID': product["id"],
                                               'Hive_NodeName': node_name})

    if len(HSC.products.hotwater) > 0:
        for product in HSC.products.hotwater:
            if ("id" in product and
                    "state" in product and
                    "name" in product["state"]):
                node_name = product["state"]["name"]
                if len(HSC.products.hotwater) == 1:
                    node_name = None

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_hotwater" in config_devices)):
                    device_count = device_count + 1
                    device_list_climate.append({'HA_DeviceType': 'HotWater',
                                                'Hive_NodeID': product["id"],
                                                'Hive_NodeName': node_name})

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_hotwater_state" in config_devices)):
                    device_count = device_count + 1
                    device_list_sensor.append({'HA_DeviceType':
                                               'HotWater_State',
                                               'Hive_NodeID': product["id"],
                                               'Hive_NodeName': node_name})

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_hotwater_mode" in config_devices)):
                    device_count = device_count + 1
                    device_list_sensor.append({'HA_DeviceType':
                                               'HotWater_Mode',
                                               'Hive_NodeID': product["id"],
                                               'Hive_NodeName': node_name})

                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_hotwater_boost" in config_devices)):
                    device_count = device_count + 1
                    device_list_sensor.append({'HA_DeviceType':
                                               'HotWater_Boost',
                                               'Hive_NodeID': product["id"],
                                               'Hive_NodeName': node_name})

    if len(HSC.devices.thermostat) > 0 or len(HSC.devices.sensors) > 0:
        all_devices = HSC.devices.thermostat + HSC.devices.sensors
        for a_device in all_devices:
            if ("id" in a_device and
                    "state" in a_device and
                    "name" in a_device["state"]):
                node_name = a_device["state"]["name"]
                if (a_device["type"] == "thermostatui" and
                        len(HSC.devices.thermostat) == 1):
                    node_name = None
                if (len(config_devices) == 0 or
                        len(config_devices) > 0 and
                        "hive_thermostat_batterylevel" or
                        len(config_devices) > 0 and
                        "hive_sensor_batterylevel" in config_devices):
                    device_count = device_count + 1
                    if "type" in a_device:
                        hive_device_type = a_device["type"]
                    device_list_sensor.append({'HA_DeviceType':
                                               'Hive_Device_BatteryLevel',
                                               'Hive_NodeID': a_device["id"],
                                               'Hive_NodeName': node_name,
                                               "Hive_DeviceType":
                                               hive_device_type})

    # pylint: disable=too-many-nested-blocks
    if len(HSC.products.light) > 0:
        for product in HSC.products.light:
            if ("id" in product and
                    "state" in product and
                    "name" in product["state"]):
                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_active_light" in config_devices)):
                    device_count = device_count + 1
                    if "type" in product:
                        light_device_type = product["type"]
                        if HSC.logging:
                            _LOGGER.warning("Adding %s, %s to device list",
                                            product["type"],
                                            product["state"]["name"])
                        device_list_light.append({'HA_DeviceType':
                                                  'Hive_Device_Light',
                                                  'Hive_Light_DeviceType':
                                                  light_device_type,
                                                  'Hive_NodeID':
                                                  product["id"],
                                                  'Hive_NodeName':
                                                  product["state"]["name"]})
                        if (len(config_devices) == 0 or
                                (len(config_devices) > 0 and
                                 "hive_active_light_sensor" in
                                 config_devices)):
                            device_list_sensor.append({'HA_DeviceType':
                                                       'Hive_Device_Mode',
                                                       'Hive_NodeID':
                                                       product["id"],
                                                       'Hive_NodeName':
                                                       product["state"]
                                                       ["name"],
                                                       "Hive_DeviceType":
                                                       light_device_type})

    # pylint: disable=too-many-nested-blocks
    if len(HSC.products.plug) > 0:
        for product in HSC.products.plug:
            if ("id" in product and
                    "state" in product and
                    "name" in product["state"]):
                if (len(config_devices) == 0 or
                        (len(config_devices) > 0 and
                         "hive_active_plug" in config_devices)):
                    device_count = device_count + 1
                    if "type" in product:
                        plug_device_type = product["type"]
                        if HSC.logging:
                            _LOGGER.warning("Adding %s, %s to device list",
                                            product["type"],
                                            product["state"]["name"])
                        device_list_plug.append({'HA_DeviceType':
                                                 'Hive_Device_Plug',
                                                 'Hive_Plug_DeviceType':
                                                 plug_device_type,
                                                 'Hive_NodeID':
                                                 product["id"],
                                                 'Hive_NodeName':
                                                 product["state"]["name"]})
                        if (len(config_devices) == 0 or
                                (len(config_devices) > 0 and
                                 "hive_active_plug_sensor" in
                                 config_devices)):
                            device_list_sensor.append({'HA_DeviceType':
                                                       'Hive_Device_Mode',
                                                       'Hive_NodeID':
                                                       product["id"],
                                                       'Hive_NodeName':
                                                       product["state"]
                                                       ["name"],
                                                       "Hive_DeviceType":
                                                       plug_device_type})

    if len(HSC.products.sensors) > 0:
        for product in HSC.products.sensors:
            if ("id" in product and
                    "state" in product and
                    "name" in product["state"]):
                if (len(config_devices) == 0 or
                        len(config_devices) > 0 and
                        "hive_active_sensor" in config_devices):
                    device_count = device_count + 1
                    if "type" in product:
                        hive_sensor_device_type = product["type"]
                    device_list_sensor.append({'HA_DeviceType':
                                               'Hive_Device_Sensor',
                                               'Hive_NodeID': product["id"],
                                               'Hive_NodeName':
                                               product["state"]["name"],
                                               "Hive_DeviceType":
                                               hive_sensor_device_type})

    global HGO

    try:
        HGO = HiveObjects()
    except RuntimeError:
        return False

    if (len(device_list_sensor) > 0 or
            len(device_list_climate) > 0 or
            len(device_list_light) > 0 or
            len(device_list_plug) > 0):
        if len(device_list_sensor) > 0:
            load_platform(hass, 'sensor', DOMAIN, device_list_sensor)
        if len(device_list_climate) > 0:
            load_platform(hass, 'climate', DOMAIN, device_list_climate)
        if len(device_list_light) > 0:
            load_platform(hass, 'light', DOMAIN, device_list_light)
        if len(device_list_plug) > 0:
            load_platform(hass, 'switch', DOMAIN, device_list_plug)
        return True


class HiveObjects():
    """Initiate the HiveObjects class to expose platform methods."""

    def __init__(self):
        """Initialize HiveObjects."""
        self.self_node_id = ""

    def update_data(self, node_id, device_type):
        """Get the latest data from the Hive API - rate limiting."""
        self.self_node_id = node_id
        hive_api_get_nodes_rl(node_id, device_type)

    def get_min_temperature(self, node_id, device_type):
        """Public get minimum target heating temperature possible."""
        self.self_node_id = node_id
        return p_get_heating_min_temp(node_id, device_type)

    def get_max_temperature(self, node_id, device_type):
        """Public get maximum target heating temperature possible."""
        self.self_node_id = node_id
        return p_get_heating_max_temp(node_id, device_type)

    def get_current_temperature(self, node_id, device_type):
        """Public get current heating temperature."""
        self.self_node_id = node_id
        return p_get_heating_current_temp(node_id, device_type)

    def get_current_temp_sa(self, node_id, device_type):
        """Public get current heating temperature state attributes."""
        self.self_node_id = node_id
        return p_get_heating_current_temp_sa(node_id, device_type)

    def get_target_temperature(self, node_id, device_type):
        """Public get current heating target temperature."""
        self.self_node_id = node_id
        return p_get_heating_target_temp(node_id, device_type)

    def get_target_temp_sa(self, node_id, device_type):
        """Public get current heating target temperature state attributes."""
        self.self_node_id = node_id
        return p_get_heating_target_temp_sa(node_id, device_type)

    def set_target_temperature(self, node_id, device_type, new_temperature):
        """Public set target heating temperature."""
        self.self_node_id = node_id
        if new_temperature is not None:
            p_hive_set_temperature(node_id, device_type, new_temperature)

    def get_heating_state(self, node_id, device_type):
        """Public get current heating state."""
        self.self_node_id = node_id
        return p_get_heating_state(node_id, device_type)

    def get_heating_state_sa(self, node_id, device_type):
        """Public get current heating state, state attributes."""
        self.self_node_id = node_id
        return p_get_heating_state_sa(node_id, device_type)

    def get_heating_mode(self, node_id, device_type):
        """Public get current heating mode."""
        self.self_node_id = node_id
        return p_get_heating_mode(node_id, device_type)

    def set_heating_mode(self, node_id, device_type, new_operation_mode):
        """Public set heating mode."""
        self.self_node_id = node_id
        p_hive_set_heating_mode(node_id, device_type, new_operation_mode)

    def get_heating_mode_sa(self, node_id, device_type):
        """Public get current heating mode state attributes."""
        self.self_node_id = node_id
        return p_get_heating_mode_sa(node_id, device_type)

    def get_heating_mode_list(self, node_id, device_type):
        """Public get possible heating modes list."""
        self.self_node_id = node_id
        return p_get_heating_operation_modes(node_id, device_type)

    def get_heating_boost(self, node_id, device_type):
        """Public get heating boost status."""
        self.self_node_id = node_id
        return p_get_heating_boost(node_id, device_type)

    def get_heating_boost_sa(self, node_id, device_type):
        """Public get heating boost status state attributes."""
        self.self_node_id = node_id
        return p_get_heating_boost_sa(node_id, device_type)

    def get_hotwater_state(self, node_id, device_type):
        """Public get current hot water state."""
        self.self_node_id = node_id
        return p_get_hotwater_state(node_id, device_type)

    def get_hotwater_state_sa(self, node_id, device_type):
        """Public get current hotwater state, state attributes."""
        self.self_node_id = node_id
        return p_get_hotwater_state_sa(node_id, device_type)

    def get_hotwater_mode(self, node_id, device_type):
        """Public get current hot water mode."""
        self.self_node_id = node_id
        return p_get_hotwater_mode(node_id, device_type)

    def get_hotwater_mode_sa(self, node_id, device_type):
        """Public get current hot water mode state attributes."""
        self.self_node_id = node_id
        return p_get_hotwater_mode_sa(node_id, device_type)

    def set_hotwater_mode(self, node_id, device_type, new_operation_mode):
        """Public set hot water mode ."""
        self.self_node_id = node_id
        p_hive_set_hotwater_mode(node_id, device_type, new_operation_mode)

    def get_hotwater_mode_list(self, node_id, device_type):
        """Public get hot water possible modes list."""
        self.self_node_id = node_id
        return p_get_hotwater_operation_modes(node_id, device_type)

    def get_hotwater_boost(self, node_id, device_type):
        """Public get current hot water boost status."""
        self.self_node_id = node_id
        return p_get_hotwater_boost(node_id, device_type)

    def get_hotwater_boost_sa(self, node_id, device_type):
        """Public get current hot water bosst status state attributes."""
        self.self_node_id = node_id
        return p_get_hotwater_boost_sa(node_id, device_type)

    def get_battery_level(self,
                          node_id,
                          node_name,
                          device_type,
                          node_device_type):
        """Public get node battery level."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Getting Battery Level for  %s", node_name)
        return p_get_device_battery_level(node_id,
                                          node_name,
                                          device_type,
                                          node_device_type)

    def get_light_state(self, node_id, device_type, node_name):
        """Public get current light state."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Getting status for  %s", node_name)
        return p_get_light_state(node_id, device_type, node_name)

    def get_light_min_color_temp(self, node_id, device_type, node_name):
        """Public get light minimum colour temperature."""
        self.self_node_id = node_id
        return p_get_light_min_color_temp(node_id, device_type, node_name)

    def get_light_max_color_temp(self, node_id, device_type, node_name):
        """Public get light maximum colour temperature."""
        self.self_node_id = node_id
        return p_get_light_max_color_temp(node_id, device_type, node_name)

    def get_light_brightness(self, node_id, device_type, node_name):
        """Public get current light brightness."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Getting brightness for  %s", node_name)
        return p_get_light_brightness(node_id, device_type, node_name)

    def get_light_color_temp(self, node_id, device_type, node_name):
        """Public get light current colour temperature."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Getting colour temperature for  %s", node_name)
        return p_get_light_color_temp(node_id, device_type, node_name)

    def set_light_turn_on(self,
                          node_id,
                          device_type,
                          node_device_type,
                          node_name,
                          new_brightness,
                          new_color_temp):
        """Public set light turn on."""
        self.self_node_id = node_id
        if HSC.logging:
            if new_brightness is None and new_color_temp is None:
                _LOGGER.warning("Switching %s light on", node_name)
            elif new_brightness is not None and new_color_temp is None:
                _LOGGER.warning("New Brightness is %s", new_brightness)
            elif new_brightness is None and new_color_temp is not None:
                _LOGGER.warning("New Colour Temprature is %s", new_color_temp)
        return p_hive_set_light_turn_on(node_id,
                                        device_type,
                                        node_device_type,
                                        node_name,
                                        new_brightness,
                                        new_color_temp)

    def set_light_turn_off(self,
                           node_id,
                           device_type,
                           node_device_type,
                           node_name):
        """Public set light turn off."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Switching %s light off", node_name)
        return p_hive_set_light_turn_off(node_id,
                                         device_type,
                                         node_device_type,
                                         node_name)

    def get_smartplug_state(self, node_id, device_type, node_name):
        """Public get current smart plug state."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Getting status for %s", node_name)
        return p_get_smartplug_state(node_id, device_type, node_name)

    def get_smartplug_power_consumption(self,
                                        node_id,
                                        device_type,
                                        node_name):
        """Public get smart plug current power consumption."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Getting current power consumption for %s",
                            node_name)
        return p_get_smartplug_power_usage(node_id, device_type, node_name)

    def set_smartplug_turn_on(self,
                              node_id,
                              device_type,
                              node_name,
                              node_device_type):
        """Public set smart plug turn on."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Switching %s on", node_name)
        return p_hive_set_smartplug_turn_on(node_id,
                                            device_type,
                                            node_name,
                                            node_device_type)

    def set_smartplug_turn_off(self,
                               node_id,
                               device_type,
                               node_name,
                               node_device_type):
        """Public set smart plug turn off."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Switching %s off", node_name)
        return p_hive_set_smartplug_turn_off(node_id,
                                             device_type,
                                             node_name,
                                             node_device_type)

    def get_sensor_state(self,
                         node_id,
                         device_type,
                         node_name,
                         node_device_type):
        """Public get current sensor state."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Getting Sensor State for  %s", node_name)
        return p_get_hive_sensor_state(node_id,
                                       device_type,
                                       node_name,
                                       node_device_type)

    def get_device_mode(self,
                        node_id,
                        device_type,
                        node_name,
                        node_device_type):
        """Public get current device mode."""
        self.self_node_id = node_id
        if HSC.logging:
            _LOGGER.warning("Getting Device Mode for  %s", node_name)
        return p_get_hive_device_mode(node_id,
                                      device_type,
                                      node_name,
                                      node_device_type)
