"""Common code for tests."""

from copy import deepcopy
import re
from typing import Any, List, NamedTuple, Optional, Union
from urllib import parse

from pyvera import (
    CATEGORY_ARMABLE,
    CATEGORY_CURTAIN,
    CATEGORY_DIMMER,
    CATEGORY_HUMIDITY_SENSOR,
    CATEGORY_LIGHT_SENSOR,
    CATEGORY_LOCK,
    CATEGORY_POWER_METER,
    CATEGORY_SCENE_CONTROLLER,
    CATEGORY_SENSOR,
    CATEGORY_SWITCH,
    CATEGORY_TEMPERATURE_SENSOR,
    CATEGORY_THERMOSTAT,
    CATEGORY_UV_SENSOR,
)
import requests_mock
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from homeassistant.components.vera import (
    CONF_CONTROLLER,
    CONF_EXCLUDE,
    CONF_LIGHTS,
    DOMAIN,
    VERA_CONTROLLER,
)
from homeassistant.const import CONF_UNIT_SYSTEM, CONF_UNIT_SYSTEM_METRIC
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

ComponentData = NamedTuple(
    "ComponentData", (("sdata", dict), ("status", dict), ("lu_sdata", dict))
)


def get_entity_id(device: dict, platform: str) -> str:
    """Get an entity id for a vera device."""
    device_name = slugify(device.get("name"))
    device_id = str(device.get("id"))
    return f"{platform}.{device_name}_{device_id}"


def find_device_object(device_id: int, data_list: list) -> Optional[dict]:
    """Find a vera device object in a list of devices."""
    for device in data_list or []:
        if device.get("id") == device_id:
            return device

    return None


def get_device(device_id: int, data: ComponentData) -> Optional[dict]:
    """Find a vera device."""
    return find_device_object(device_id, data.sdata.get("devices"))


def get_device_status(device_id: int, data: ComponentData) -> Optional[dict]:
    """Find a vera device status."""
    return find_device_object(device_id, data.status.get("devices"))


async def update_device(
    hass: HomeAssistant, data: ComponentData, device_id: int, key: str, value: Any
) -> None:
    """Update a vera device with a specific key/value."""
    device = get_device(device_id, data)
    assert device, "Failed to find device with device id %d" % device_id

    device_status = get_device_status(device_id, data)
    assert device_status, "Failed to find device status with device id %d" % device_id

    device_status[key] = value
    device[key] = value

    await publish_device_status(hass, device_status)


async def publish_device_status(hass: HomeAssistant, device_status: dict) -> None:
    """Instruct pyvera to notify objects that data changed for a device."""
    controller = hass.data[VERA_CONTROLLER]
    # pylint: disable=protected-access
    controller.subscription_registry._event([device_status], [])
    await hass.async_block_till_done()


def assert_state(
    hass: HomeAssistant,
    data: ComponentData,
    device_id: int,
    platform: str,
    expected_state: Union[None, str, int, float] = None,
    expected_brightness: Optional[int] = None,
    expected_hs_color: Optional[List[int]] = None,
    expected_hvac_mode: Optional[str] = None,
    expected_fan_mode: Optional[str] = None,
    expected_temperature: Optional[int] = None,
    expected_current_temperature: Optional[int] = None,
    expected_min_temp: Optional[int] = None,
    expected_max_temp: Optional[int] = None,
    expected_current_position: Optional[int] = None,
) -> None:
    """Assert various aspects of an HA state."""
    device = get_device(device_id, data)
    assert device, "Failed to find device with id %d" % device_id

    entity_id = get_entity_id(device, platform)

    state = hass.states.get(entity_id)  # type: State
    assert state, f"Unknown entity {entity_id}"

    if expected_state is not None:
        assert (
            state.state == expected_state
        ), f"Expected '{expected_state}' (type {type(expected_state)}) but was '{state.state}' (type {type(state.state)}) for entity '{entity_id}'"

    if expected_brightness is not None:
        assert_state_attribute(state, "brightness", expected_brightness)

    if expected_hs_color is not None:
        assert_state_attribute(state, "hs_color", expected_hs_color)

    if expected_hvac_mode is not None:
        assert_state_attribute(state, "hvac_mode", expected_hvac_mode)

    if expected_fan_mode is not None:
        assert_state_attribute(state, "fan_mode", expected_fan_mode)

    if expected_temperature is not None:
        assert_state_attribute(state, "temperature", expected_temperature)

    if expected_current_temperature is not None:
        assert_state_attribute(
            state, "current_temperature", expected_current_temperature
        )

    if expected_min_temp is not None:
        assert_state_attribute(state, "min_temp", expected_min_temp)

    if expected_max_temp is not None:
        assert_state_attribute(state, "max_temp", expected_max_temp)

    if expected_current_position is not None:
        assert_state_attribute(state, "current_position", expected_current_position)


def assert_state_attribute(state: State, attribute: str, expected: Any) -> None:
    """Assert a state's attribute has a specific value."""
    assert attribute in state.attributes, f"Attribute '{attribute}' was not found."

    value = state.attributes.get(attribute)
    assert (
        value == expected
    ), f"Expected {attribute} '{expected}', but was '{value}' for entity '{state.entity_id}'"


async def async_call_service(
    hass: HomeAssistant,
    data: ComponentData,
    device_id: int,
    platform: str,
    service: str,
    extra_attribs: dict = None,
) -> None:
    """Call an HA service for a vera device."""
    await hass.services.async_call(
        platform,
        service,
        {
            **{"entity_id": get_entity_id(get_device(device_id, data), platform)},
            **(extra_attribs or {}),
        },
    )

    await hass.async_block_till_done()


async def async_configure_component(
    hass: HomeAssistant,
    requests_mocker: requests_mock.Mocker,
    response_sdata: dict,
    response_status: dict,
    respone_lu_sdata: dict,
) -> ComponentData:
    """Configure the component with specific mock data."""
    controller_url = "http://127.0.0.1:123"

    component_data = ComponentData(
        sdata=deepcopy(response_sdata),
        status=deepcopy(response_status),
        lu_sdata=deepcopy(respone_lu_sdata),
    )

    requests_mocker.get(
        re.compile(controller_url + "/data_request?.*id=sdata(&.*|$)"),
        json=component_data.sdata,
        status_code=200,
    )

    requests_mocker.get(
        re.compile(controller_url + "/data_request?.*id=status(&.*|$)"),
        json=component_data.status,
        status_code=200,
    )

    requests_mocker.get(
        re.compile(controller_url + "/data_request?.*id=lu_sdata(&.*|$)"),
        json=component_data.lu_sdata,
        status_code=200,
    )

    requests_mocker.get(
        re.compile(controller_url + "/data_request?.*id=action(&.*|$)"),
        json={},
        status_code=200,
    )

    def variable_get_callback(request: _RequestObjectProxy, context: _Context):
        nonlocal component_data
        params = parse.parse_qs(request.query)
        device_id = int(params.pop("DeviceNum")[0])
        variable = params.pop("Variable")[0]

        context.status_code = 200

        status = get_device_status(device_id, component_data)
        for state in status.get("states", []):
            if state.get("variable") == variable:
                return state.get("value")

        return ""

    requests_mocker.register_uri(
        "GET",
        re.compile(controller_url + "/data_request?.*id=variableget(&.*|$)"),
        text=variable_get_callback,
    )

    def lu_action_callback(request: _RequestObjectProxy, context: _Context):
        nonlocal component_data
        params = parse.parse_qs(request.query)
        params.pop("id")
        service_id = params.pop("serviceId")[0]
        action = params.pop("action")[0]
        device_id = int(params.pop("DeviceNum")[0])
        params.pop("output_format")
        set_state_variable_name = next(
            key for key in params if key.lower().startswith("new")
        )
        state_variable_name = set_state_variable_name[3:]
        state_variable_value = params.pop(set_state_variable_name)[0]
        status_variable_name = None

        if service_id == "urn:upnp-org:serviceId:SwitchPower1":
            if action == "SetTarget":
                status_variable_name = "status"
        elif service_id == "urn:upnp-org:serviceId:Dimming1":
            if action == "SetLoadLevelTarget":
                status_variable_name = "level"
        elif service_id == "urn:micasaverde-com:serviceId:SecuritySensor1":
            if action == "SetArmed":
                status_variable_name = "armed"
        elif service_id == "urn:upnp-org:serviceId:WindowCovering1":
            if action == "SetLoadLevelTarget":
                status_variable_name = "level"
        elif service_id == "urn:micasaverde-com:serviceId:DoorLock1":
            if action == "NewTarget":
                status_variable_name = "locked"
        elif service_id == "urn:upnp-org:serviceId:HVAC_UserOperatingMode1":
            if action == "SetModeTarget":
                status_variable_name = "mode"
        elif service_id == "urn:upnp-org:serviceId:HVAC_FanOperatingMode1":
            if action == "SetMode":
                status_variable_name = "fanmode"
        elif service_id == "urn:upnp-org:serviceId:TemperatureSetpoint1_Cool":
            pass
        elif service_id == "urn:upnp-org:serviceId:TemperatureSetpoint1_Heat":
            pass
        elif service_id == "urn:upnp-org:serviceId:TemperatureSetpoint1":
            if action == "SetCurrentSetpoint":
                status_variable_name = "setpoint"
        elif service_id == "urn:micasaverde-com:serviceId:Color1":
            if action == "SetColorRGB":
                status_variable_name = "CurrentColor"

        device = get_device(device_id, component_data)
        status = get_device_status(device_id, component_data)

        # Update the device and status objects.
        if status_variable_name is not None:
            device[status_variable_name] = state_variable_value
            status[status_variable_name] = state_variable_value

        # Update the state object.
        status["states"] = [
            state
            for state in status.get("states", [])
            if state.get("service") != service_id
            and state.get("variable") != state_variable_name
        ]
        status["states"].append(
            {
                "service": service_id,
                "variable": state_variable_name,
                "value": state_variable_value,
            }
        )

        context.status_code = 200
        return {}

    requests_mocker.register_uri(
        "GET",
        re.compile(controller_url + "/data_request?.+id=lu_action"),
        json=lu_action_callback,
    )

    # Setup home assistant.
    hass_config = {
        "homeassistant": {CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC},
        DOMAIN: {
            CONF_CONTROLLER: controller_url,
            CONF_EXCLUDE: [DEVICE_IGNORE],
            CONF_LIGHTS: [DEVICE_SWITCH2_ID],
        },
    }

    assert await async_setup_component(hass, DOMAIN, hass_config)
    await hass.async_block_till_done()

    return component_data


RESPONSE_SDATA_EMPTY = {"scenes": (), "categories": (), "devices": ()}
RESPONSE_STATUS_EMPTY = {"devices": ()}
RESPONSE_LU_SDATA_EMPTY = {}
RESPONSE_DEVICES_EMPTY = {}
RESPONSE_SCENES_EMPTY = {}

SCENE1_ID = 101

DEVICE_IGNORE = 55
DEVICE_ALARM_SENSOR_ID = 62
DEVICE_DOOR_SENSOR_ID = 45
DEVICE_MOTION_SENSOR_ID = 51
DEVICE_TEMP_SENSOR_ID = 52
DEVICE_DIMMER_ID = 59
DEVICE_LIGHT_ID = 69
DEVICE_SWITCH_ID = 44
DEVICE_SWITCH2_ID = 46
DEVICE_LOCK_ID = 10
DEVICE_THERMOSTAT_ID = 11
DEVICE_CURTAIN_ID = 12
DEVICE_SCENE_CONTROLLER_ID = 13
DEVICE_LIGHT_SENSOR_ID = 14
DEVICE_UV_SENSOR_ID = 15
DEVICE_HUMIDITY_SENSOR_ID = 16
DEVICE_POWER_METER_SENSOR_ID = 17

CATEGORY_GENERIC = 11
CATEGORY_UNKNOWN = 1234

RESPONSE_SDATA = {
    "scenes": [{"id": SCENE1_ID, "name": "scene1", "active": 0, "root": 0}],
    "temperature": 23,
    "categories": [
        {"name": "Dimmable Switch", "id": CATEGORY_DIMMER},
        {"name": "On/Off Switch", "id": CATEGORY_SWITCH},
        {"name": "Sensor", "id": CATEGORY_ARMABLE},
        {"name": "Generic IO", "id": CATEGORY_GENERIC},
        {"name": "Temperature Sensor", "id": CATEGORY_TEMPERATURE_SENSOR},
        {"name": "Lock", "id": CATEGORY_LOCK},
        {"name": "Thermostat", "id": CATEGORY_THERMOSTAT},
        {"name": "Light sensor", "id": CATEGORY_LIGHT_SENSOR},
        {"name": "UV sensor", "id": CATEGORY_UV_SENSOR},
        {"name": "Humidity sensor", "id": CATEGORY_HUMIDITY_SENSOR},
        {"name": "Power meter", "id": CATEGORY_POWER_METER},
    ],
    "devices": [
        {
            "name": "Ignore 1",
            "altid": "6",
            "id": DEVICE_IGNORE,
            "category": CATEGORY_SWITCH,
            "subcategory": 1,
            "room": 0,
            "parent": 1,
            "armed": "0",
            "armedtripped": "0",
            "configured": "1",
            "batterylevel": "100",
            "commFailure": "0",
            "lasttrip": "1571790666",
            "tripped": "0",
            "state": -1,
            "comment": "",
        },
        {
            "name": "Door sensor 1",
            "altid": "6",
            "id": DEVICE_DOOR_SENSOR_ID,
            "category": CATEGORY_ARMABLE,
            "subcategory": 1,
            "room": 0,
            "parent": 1,
            "armed": "0",
            "armedtripped": "0",
            "configured": "1",
            "batterylevel": "100",
            "commFailure": "0",
            "lasttrip": "1571790666",
            "tripped": "0",
            "state": -1,
            "comment": "",
        },
        {
            "name": "Motion sensor 1",
            "altid": "12",
            "id": DEVICE_MOTION_SENSOR_ID,
            "category": CATEGORY_ARMABLE,
            "subcategory": 3,
            "room": 0,
            "parent": 1,
            "armed": "0",
            "armedtripped": "0",
            "configured": "1",
            "batterylevel": "100",
            "commFailure": "0",
            "lasttrip": "1571975359",
            "tripped": "0",
            "state": -1,
            "comment": "",
        },
        {
            "name": "Temp sensor 1",
            "altid": "m1",
            "id": DEVICE_TEMP_SENSOR_ID,
            "category": CATEGORY_TEMPERATURE_SENSOR,
            "subcategory": 0,
            "room": 0,
            "parent": 51,
            "configured": "0",
            "temperature": "57.00",
        },
        {
            "name": "Dimmer 1",
            "altid": "16",
            "id": DEVICE_DIMMER_ID,
            "category": CATEGORY_DIMMER,
            "subcategory": 2,
            "room": 0,
            "parent": 1,
            "kwh": "0.0000",
            "watts": "0",
            "configured": "1",
            "level": "0",
            "status": "0",
            "state": -1,
            "comment": "",
        },
        {
            "name": "Light 1",
            "altid": "16",
            "id": DEVICE_LIGHT_ID,
            "category": CATEGORY_DIMMER,
            "subcategory": 2,
            "room": 0,
            "parent": 1,
            "kwh": "0.0000",
            "watts": "0",
            "configured": "1",
            "level": "0",
            "status": "0",
            "state": -1,
            "comment": "",
        },
        {
            "name": "Switch 1",
            "altid": "5",
            "id": DEVICE_SWITCH_ID,
            "category": CATEGORY_SWITCH,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "comment": "",
        },
        {
            "name": "Switch 2",
            "altid": "5",
            "id": DEVICE_SWITCH2_ID,
            "category": CATEGORY_SWITCH,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "comment": "",
        },
        {
            "name": "Lock 1",
            "altid": "5",
            "id": DEVICE_LOCK_ID,
            "category": CATEGORY_LOCK,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "comment": "",
            "locked": "0",
        },
        {
            "name": "Thermostat 1",
            "altid": "5",
            "id": DEVICE_THERMOSTAT_ID,
            "category": CATEGORY_THERMOSTAT,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "mode": "Off",
            "fanmode": "Off",
            "setpoint": 8,
            "temperature": 9,
            "watts": 23,
            "comment": "",
        },
        {
            "name": "Curtain 1",
            "altid": "5",
            "id": DEVICE_CURTAIN_ID,
            "category": CATEGORY_CURTAIN,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "level": 0,
            "comment": "",
        },
        {
            "name": "Scene 1",
            "altid": "5",
            "id": DEVICE_SCENE_CONTROLLER_ID,
            "category": CATEGORY_SCENE_CONTROLLER,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            # "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "active": 0,
            "comment": "",
        },
        {
            "name": "Alarm sensor 1",
            "altid": "18",
            "id": DEVICE_ALARM_SENSOR_ID,
            "category": CATEGORY_SENSOR,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "batterylevel": "100",
            "commFailure": "0",
            "armed": "0",
            "armedtripped": "0",
            "state": -1,
            "tripped": "0",
            "comment": "",
        },
        {
            "name": "Light sensor 1",
            "altid": "5",
            "id": DEVICE_LIGHT_SENSOR_ID,
            "category": CATEGORY_LIGHT_SENSOR,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "light": "0",
            "comment": "",
        },
        {
            "name": "UV sensor 1",
            "altid": "5",
            "id": DEVICE_UV_SENSOR_ID,
            "category": CATEGORY_UV_SENSOR,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "light": "0",
            "comment": "",
        },
        {
            "name": "Humidity sensor 1",
            "altid": "5",
            "id": DEVICE_HUMIDITY_SENSOR_ID,
            "category": CATEGORY_HUMIDITY_SENSOR,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "humidity": "0",
            "comment": "",
        },
        {
            "name": "Power meter sensor 1",
            "altid": "5",
            "id": DEVICE_POWER_METER_SENSOR_ID,
            "category": CATEGORY_POWER_METER,
            "subcategory": 0,
            "room": 0,
            "parent": 1,
            "configured": "1",
            "commFailure": "0",
            "armedtripped": "1",
            "lasttrip": "1561049427",
            "tripped": "1",
            "armed": "0",
            "status": "0",
            "state": -1,
            "watts": "0",
            "comment": "",
        },
    ],
}

RESPONSE_STATUS = {
    "startup": {"tasks": []},
    "devices": [
        {
            "id": DEVICE_DOOR_SENSOR_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "armed": "0",
        },
        {
            "id": DEVICE_MOTION_SENSOR_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "armed": "0",
        },
        {
            "id": DEVICE_TEMP_SENSOR_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_DIMMER_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_LIGHT_ID,
            "states": [
                {
                    "service": "urn:micasaverde-com:serviceId:Color1",
                    "variable": "CurrentColor",
                    "value": "R=255,G=100,B=100",
                },
                {
                    "service": "urn:micasaverde-com:serviceId:Color1",
                    "variable": "SupportedColors",
                    "value": "R,G,B",
                },
            ],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_SWITCH_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_SWITCH2_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_LOCK_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
            "locked": "0",
        },
        {
            "id": DEVICE_THERMOSTAT_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_CURTAIN_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_SCENE_CONTROLLER_ID,
            "states": [
                {"service": "", "variable": "LastSceneID", "value": "1234"},
                {"service": "", "variable": "LastSceneTime", "value": "10000012"},
            ],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_ALARM_SENSOR_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_LIGHT_SENSOR_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_UV_SENSOR_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_HUMIDITY_SENSOR_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
        {
            "id": DEVICE_POWER_METER_SENSOR_ID,
            "states": [],
            "Jobs": [],
            "PendingJobs": 0,
            "tooltip": {"display": 0},
            "status": -1,
        },
    ],
}

RESPONSE_SCENES = {}
