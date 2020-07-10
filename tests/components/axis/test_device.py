"""Test Axis device."""
from copy import deepcopy
import json
from unittest import mock

import axis as axislib
from axis.api_discovery import URL as API_DISCOVERY_URL
from axis.basic_device_info import URL as BASIC_DEVICE_INFO_URL
from axis.event_stream import OPERATION_INITIALIZED
from axis.light_control import URL as LIGHT_CONTROL_URL
from axis.mqtt import URL_CLIENT as MQTT_CLIENT_URL
from axis.param_cgi import (
    BRAND as BRAND_URL,
    INPUT as INPUT_URL,
    IOPORT as IOPORT_URL,
    OUTPUT as OUTPUT_URL,
    PROPERTIES as PROPERTIES_URL,
    STREAM_PROFILES as STREAM_PROFILES_URL,
)
from axis.port_management import URL as PORT_MANAGEMENT_URL
import pytest

from homeassistant import config_entries
from homeassistant.components import axis
from homeassistant.components.axis.const import (
    CONF_EVENTS,
    CONF_MODEL,
    DOMAIN as AXIS_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from tests.async_mock import Mock, patch
from tests.common import MockConfigEntry, async_fire_mqtt_message

MAC = "00408C12345"
MODEL = "model"
NAME = "name"

ENTRY_OPTIONS = {CONF_EVENTS: True}

ENTRY_CONFIG = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "root",
    CONF_PASSWORD: "pass",
    CONF_PORT: 80,
    CONF_MAC: MAC,
    CONF_MODEL: MODEL,
    CONF_NAME: NAME,
}

API_DISCOVERY_RESPONSE = {
    "method": "getApiList",
    "apiVersion": "1.0",
    "data": {
        "apiList": [
            {"id": "api-discovery", "version": "1.0", "name": "API Discovery Service"},
            {"id": "param-cgi", "version": "1.0", "name": "Legacy Parameter Handling"},
        ]
    },
}

API_DISCOVERY_BASIC_DEVICE_INFO = {
    "id": "basic-device-info",
    "version": "1.1",
    "name": "Basic Device Information",
}
API_DISCOVERY_MQTT = {"id": "mqtt-client", "version": "1.0", "name": "MQTT Client API"}
API_DISCOVERY_PORT_MANAGEMENT = {
    "id": "io-port-management",
    "version": "1.0",
    "name": "IO Port Management",
}

BASIC_DEVICE_INFO_RESPONSE = {
    "apiVersion": "1.1",
    "data": {
        "propertyList": {
            "ProdNbr": "M1065-LW",
            "ProdType": "Network Camera",
            "SerialNumber": "00408C12345",
            "Version": "9.80.1",
        }
    },
}

LIGHT_CONTROL_RESPONSE = {
    "apiVersion": "1.1",
    "method": "getLightInformation",
    "data": {
        "items": [
            {
                "lightID": "led0",
                "lightType": "IR",
                "enabled": True,
                "synchronizeDayNightMode": True,
                "lightState": False,
                "automaticIntensityMode": False,
                "automaticAngleOfIlluminationMode": False,
                "nrOfLEDs": 1,
                "error": False,
                "errorInfo": "",
            }
        ]
    },
}

MQTT_CLIENT_RESPONSE = {
    "apiVersion": "1.0",
    "context": "some context",
    "method": "getClientStatus",
    "data": {"status": {"state": "active", "connectionStatus": "Connected"}},
}

PORT_MANAGEMENT_RESPONSE = {
    "apiVersion": "1.0",
    "method": "getPorts",
    "data": {
        "numberOfPorts": 1,
        "items": [
            {
                "port": "0",
                "configurable": False,
                "usage": "",
                "name": "PIR sensor",
                "direction": "input",
                "state": "open",
                "normalState": "open",
            }
        ],
    },
}

BRAND_RESPONSE = """root.Brand.Brand=AXIS
root.Brand.ProdFullName=AXIS M1065-LW Network Camera
root.Brand.ProdNbr=M1065-LW
root.Brand.ProdShortName=AXIS M1065-LW
root.Brand.ProdType=Network Camera
root.Brand.ProdVariant=
root.Brand.WebURL=http://www.axis.com
"""

PORTS_RESPONSE = """root.Input.NbrOfInputs=1
root.IOPort.I0.Configurable=no
root.IOPort.I0.Direction=input
root.IOPort.I0.Input.Name=PIR sensor
root.IOPort.I0.Input.Trig=closed
root.Output.NbrOfOutputs=0
"""

PROPERTIES_RESPONSE = """root.Properties.API.HTTP.Version=3
root.Properties.API.Metadata.Metadata=yes
root.Properties.API.Metadata.Version=1.0
root.Properties.Firmware.BuildDate=Feb 15 2019 09:42
root.Properties.Firmware.BuildNumber=26
root.Properties.Firmware.Version=9.10.1
root.Properties.Image.Format=jpeg,mjpeg,h264
root.Properties.Image.NbrOfViews=2
root.Properties.Image.Resolution=1920x1080,1280x960,1280x720,1024x768,1024x576,800x600,640x480,640x360,352x240,320x240
root.Properties.Image.Rotation=0,180
root.Properties.System.SerialNumber=00408C12345
"""

STREAM_PROFILES_RESPONSE = """root.StreamProfile.MaxGroups=26
root.StreamProfile.S0.Description=profile_1_description
root.StreamProfile.S0.Name=profile_1
root.StreamProfile.S0.Parameters=videocodec=h264
root.StreamProfile.S1.Description=profile_2_description
root.StreamProfile.S1.Name=profile_2
root.StreamProfile.S1.Parameters=videocodec=h265
"""


def vapix_session_request(session, url, **kwargs):
    """Return data based on url."""
    if API_DISCOVERY_URL in url:
        return json.dumps(API_DISCOVERY_RESPONSE)
    if BASIC_DEVICE_INFO_URL in url:
        return json.dumps(BASIC_DEVICE_INFO_RESPONSE)
    if LIGHT_CONTROL_URL in url:
        return json.dumps(LIGHT_CONTROL_RESPONSE)
    if MQTT_CLIENT_URL in url:
        return json.dumps(MQTT_CLIENT_RESPONSE)
    if PORT_MANAGEMENT_URL in url:
        return json.dumps(PORT_MANAGEMENT_RESPONSE)
    if BRAND_URL in url:
        return BRAND_RESPONSE
    if IOPORT_URL in url or INPUT_URL in url or OUTPUT_URL in url:
        return PORTS_RESPONSE
    if PROPERTIES_URL in url:
        return PROPERTIES_RESPONSE
    if STREAM_PROFILES_URL in url:
        return STREAM_PROFILES_RESPONSE


async def setup_axis_integration(hass, config=ENTRY_CONFIG, options=ENTRY_OPTIONS):
    """Create the Axis device."""
    config_entry = MockConfigEntry(
        domain=AXIS_DOMAIN,
        data=deepcopy(config),
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        options=deepcopy(options),
        entry_id="1",
        version=2,
    )
    config_entry.add_to_hass(hass)

    with patch("axis.vapix.session_request", new=vapix_session_request), patch(
        "axis.rtsp.RTSPClient.start", return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return hass.data[AXIS_DOMAIN].get(config_entry.unique_id)


async def test_device_setup(hass):
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        device = await setup_axis_integration(hass)

    assert device.api.vapix.firmware_version == "9.10.1"
    assert device.api.vapix.product_number == "M1065-LW"
    assert device.api.vapix.product_type == "Network Camera"
    assert device.api.vapix.serial_number == "00408C12345"

    entry = device.config_entry

    assert len(forward_entry_setup.mock_calls) == 4
    assert forward_entry_setup.mock_calls[0][1] == (entry, "binary_sensor")
    assert forward_entry_setup.mock_calls[1][1] == (entry, "camera")
    assert forward_entry_setup.mock_calls[2][1] == (entry, "light")
    assert forward_entry_setup.mock_calls[3][1] == (entry, "switch")

    assert device.host == ENTRY_CONFIG[CONF_HOST]
    assert device.model == ENTRY_CONFIG[CONF_MODEL]
    assert device.name == ENTRY_CONFIG[CONF_NAME]
    assert device.serial == ENTRY_CONFIG[CONF_MAC]


async def test_device_info(hass):
    """Verify other path of device information works."""
    api_discovery = deepcopy(API_DISCOVERY_RESPONSE)
    api_discovery["data"]["apiList"].append(API_DISCOVERY_BASIC_DEVICE_INFO)

    with patch.dict(API_DISCOVERY_RESPONSE, api_discovery):
        device = await setup_axis_integration(hass)

    assert device.api.vapix.firmware_version == "9.80.1"
    assert device.api.vapix.product_number == "M1065-LW"
    assert device.api.vapix.product_type == "Network Camera"
    assert device.api.vapix.serial_number == "00408C12345"


async def test_device_support_mqtt(hass, mqtt_mock):
    """Successful setup."""
    api_discovery = deepcopy(API_DISCOVERY_RESPONSE)
    api_discovery["data"]["apiList"].append(API_DISCOVERY_MQTT)

    with patch.dict(API_DISCOVERY_RESPONSE, api_discovery):
        await setup_axis_integration(hass)

    mqtt_mock.async_subscribe.assert_called_with(f"{MAC}/#", mock.ANY, 0, "utf-8")

    topic = f"{MAC}/event/tns:onvif/Device/tns:axis/Sensor/PIR/$source/sensor/0"
    message = b'{"timestamp": 1590258472044, "topic": "onvif:Device/axis:Sensor/PIR", "message": {"source": {"sensor": "0"}, "key": {}, "data": {"state": "1"}}}'

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 0
    async_fire_mqtt_message(hass, topic, message)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1

    pir = hass.states.get(f"binary_sensor.{NAME}_pir_0")
    assert pir.state == "on"
    assert pir.name == f"{NAME} PIR 0"


async def test_update_address(hass):
    """Test update address works."""
    device = await setup_axis_integration(hass)
    assert device.api.config.host == "1.2.3.4"

    await hass.config_entries.flow.async_init(
        AXIS_DOMAIN,
        data={
            "host": "2.3.4.5",
            "port": 80,
            "hostname": "name",
            "properties": {"macaddress": MAC},
        },
        context={"source": "zeroconf"},
    )
    await hass.async_block_till_done()

    assert device.api.config.host == "2.3.4.5"


async def test_device_unavailable(hass):
    """Successful setup."""
    device = await setup_axis_integration(hass)
    device.async_connection_status_callback(status=False)
    assert not device.available


async def test_device_reset(hass):
    """Successfully reset device."""
    device = await setup_axis_integration(hass)
    result = await device.async_reset()
    assert result is True


async def test_device_not_accessible(hass):
    """Failed setup schedules a retry of setup."""
    with patch.object(axis.device, "get_device", side_effect=axis.errors.CannotConnect):
        await setup_axis_integration(hass)
    assert hass.data[AXIS_DOMAIN] == {}


async def test_device_unknown_error(hass):
    """Unknown errors are handled."""
    with patch.object(axis.device, "get_device", side_effect=Exception):
        await setup_axis_integration(hass)
    assert hass.data[AXIS_DOMAIN] == {}


async def test_new_event_sends_signal(hass):
    """Make sure that new event send signal."""
    entry = Mock()
    entry.data = ENTRY_CONFIG

    axis_device = axis.device.AxisNetworkDevice(hass, entry)

    with patch.object(axis.device, "async_dispatcher_send") as mock_dispatch_send:
        axis_device.async_event_callback(action=OPERATION_INITIALIZED, event_id="event")
        await hass.async_block_till_done()

    assert len(mock_dispatch_send.mock_calls) == 1
    assert len(mock_dispatch_send.mock_calls[0]) == 3


async def test_shutdown():
    """Successful shutdown."""
    hass = Mock()
    entry = Mock()
    entry.data = ENTRY_CONFIG

    axis_device = axis.device.AxisNetworkDevice(hass, entry)
    axis_device.api = Mock()

    axis_device.shutdown(None)

    assert len(axis_device.api.stream.stop.mock_calls) == 1


async def test_get_device_fails(hass):
    """Device unauthorized yields authentication required error."""
    with patch(
        "axis.vapix.session_request", side_effect=axislib.Unauthorized
    ), pytest.raises(axis.errors.AuthenticationRequired):
        await axis.device.get_device(hass, host="", port="", username="", password="")


async def test_get_device_device_unavailable(hass):
    """Device unavailable yields cannot connect error."""
    with patch(
        "axis.vapix.session_request", side_effect=axislib.RequestError
    ), pytest.raises(axis.errors.CannotConnect):
        await axis.device.get_device(hass, host="", port="", username="", password="")


async def test_get_device_unknown_error(hass):
    """Device yield unknown error."""
    with patch(
        "axis.vapix.session_request", side_effect=axislib.AxisException
    ), pytest.raises(axis.errors.AuthenticationRequired):
        await axis.device.get_device(hass, host="", port="", username="", password="")
