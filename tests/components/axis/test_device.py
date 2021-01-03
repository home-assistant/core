"""Test Axis device."""
from copy import deepcopy
from unittest import mock
from unittest.mock import Mock, patch

import axis as axislib
from axis.event_stream import OPERATION_INITIALIZED
import pytest
import respx

from homeassistant import config_entries
from homeassistant.components import axis
from homeassistant.components.axis.const import (
    CONF_EVENTS,
    CONF_MODEL,
    DOMAIN as AXIS_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    STATE_ON,
)

from tests.common import MockConfigEntry, async_fire_mqtt_message

MAC = "00408C12345"
MODEL = "model"
NAME = "name"

DEFAULT_HOST = "1.2.3.4"

ENTRY_OPTIONS = {CONF_EVENTS: True}

ENTRY_CONFIG = {
    CONF_HOST: DEFAULT_HOST,
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

APPLICATIONS_LIST_RESPONSE = """<reply result="ok">
 <application Name="vmd" NiceName="AXIS Video Motion Detection" Vendor="Axis Communications" Version="4.2-0" ApplicationID="143440" License="None" Status="Running" ConfigurationPage="local/vmd/config.html" VendorHomePage="http://www.axis.com" />
</reply>"""

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

VMD4_RESPONSE = {
    "apiVersion": "1.4",
    "method": "getConfiguration",
    "context": "Axis library",
    "data": {
        "cameras": [{"id": 1, "rotation": 0, "active": True}],
        "profiles": [
            {"filters": [], "camera": 1, "triggers": [], "name": "Profile 1", "uid": 1}
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

IMAGE_RESPONSE = """root.Image.I0.Enabled=yes
root.Image.I0.Name=View Area 1
root.Image.I0.Source=0
root.Image.I1.Enabled=no
root.Image.I1.Name=View Area 2
root.Image.I1.Source=0
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
root.Properties.EmbeddedDevelopment.Version=2.16
root.Properties.Firmware.BuildDate=Feb 15 2019 09:42
root.Properties.Firmware.BuildNumber=26
root.Properties.Firmware.Version=9.10.1
root.Properties.Image.Format=jpeg,mjpeg,h264
root.Properties.Image.NbrOfViews=2
root.Properties.Image.Resolution=1920x1080,1280x960,1280x720,1024x768,1024x576,800x600,640x480,640x360,352x240,320x240
root.Properties.Image.Rotation=0,180
root.Properties.System.SerialNumber=00408C12345
"""

PTZ_RESPONSE = ""


STREAM_PROFILES_RESPONSE = """root.StreamProfile.MaxGroups=26
root.StreamProfile.S0.Description=profile_1_description
root.StreamProfile.S0.Name=profile_1
root.StreamProfile.S0.Parameters=videocodec=h264
root.StreamProfile.S1.Description=profile_2_description
root.StreamProfile.S1.Name=profile_2
root.StreamProfile.S1.Parameters=videocodec=h265
"""

VIEW_AREAS_RESPONSE = {"apiVersion": "1.0", "method": "list", "data": {"viewAreas": []}}


def mock_default_vapix_requests(respx: respx, host: str = DEFAULT_HOST) -> None:
    """Mock default Vapix requests responses."""
    respx.post(f"http://{host}:80/axis-cgi/apidiscovery.cgi").respond(
        json=API_DISCOVERY_RESPONSE,
    )
    respx.post(f"http://{host}:80/axis-cgi/basicdeviceinfo.cgi").respond(
        json=BASIC_DEVICE_INFO_RESPONSE,
    )
    respx.post(f"http://{host}:80/axis-cgi/io/portmanagement.cgi").respond(
        json=PORT_MANAGEMENT_RESPONSE,
    )
    respx.post(f"http://{host}:80/axis-cgi/lightcontrol.cgi").respond(
        json=LIGHT_CONTROL_RESPONSE,
    )
    respx.post(f"http://{host}:80/axis-cgi/mqtt/client.cgi").respond(
        json=MQTT_CLIENT_RESPONSE,
    )
    respx.post(f"http://{host}:80/axis-cgi/streamprofile.cgi").respond(
        json=STREAM_PROFILES_RESPONSE,
    )
    respx.post(f"http://{host}:80/axis-cgi/viewarea/info.cgi").respond(
        json=VIEW_AREAS_RESPONSE
    )
    respx.get(
        f"http://{host}:80/axis-cgi/param.cgi?action=list&group=root.Brand"
    ).respond(
        text=BRAND_RESPONSE,
        headers={"Content-Type": "text/plain"},
    )
    respx.get(
        f"http://{host}:80/axis-cgi/param.cgi?action=list&group=root.Image"
    ).respond(
        text=IMAGE_RESPONSE,
        headers={"Content-Type": "text/plain"},
    )
    respx.get(
        f"http://{host}:80/axis-cgi/param.cgi?action=list&group=root.Input"
    ).respond(
        text=PORTS_RESPONSE,
        headers={"Content-Type": "text/plain"},
    )
    respx.get(
        f"http://{host}:80/axis-cgi/param.cgi?action=list&group=root.IOPort"
    ).respond(
        text=PORTS_RESPONSE,
        headers={"Content-Type": "text/plain"},
    )
    respx.get(
        f"http://{host}:80/axis-cgi/param.cgi?action=list&group=root.Output"
    ).respond(
        text=PORTS_RESPONSE,
        headers={"Content-Type": "text/plain"},
    )
    respx.get(
        f"http://{host}:80/axis-cgi/param.cgi?action=list&group=root.Properties"
    ).respond(
        text=PROPERTIES_RESPONSE,
        headers={"Content-Type": "text/plain"},
    )
    respx.get(
        f"http://{host}:80/axis-cgi/param.cgi?action=list&group=root.PTZ"
    ).respond(
        text=PTZ_RESPONSE,
        headers={"Content-Type": "text/plain"},
    )
    respx.get(
        f"http://{host}:80/axis-cgi/param.cgi?action=list&group=root.StreamProfile"
    ).respond(
        text=STREAM_PROFILES_RESPONSE,
        headers={"Content-Type": "text/plain"},
    )
    respx.post(f"http://{host}:80/axis-cgi/applications/list.cgi").respond(
        text=APPLICATIONS_LIST_RESPONSE,
        headers={"Content-Type": "text/xml"},
    )
    respx.post(f"http://{host}:80/local/vmd/control.cgi").respond(json=VMD4_RESPONSE)


async def setup_axis_integration(hass, config=ENTRY_CONFIG, options=ENTRY_OPTIONS):
    """Create the Axis device."""
    config_entry = MockConfigEntry(
        domain=AXIS_DOMAIN,
        data=deepcopy(config),
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        options=deepcopy(options),
        version=2,
    )
    config_entry.add_to_hass(hass)

    with patch("axis.rtsp.RTSPClient.start", return_value=True), respx.mock:
        mock_default_vapix_requests(respx)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def test_device_setup(hass):
    """Successful setup."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        config_entry = await setup_axis_integration(hass)
        device = hass.data[AXIS_DOMAIN][config_entry.unique_id]

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
        config_entry = await setup_axis_integration(hass)
        device = hass.data[AXIS_DOMAIN][config_entry.unique_id]

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

    pir = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_pir_0")
    assert pir.state == STATE_ON
    assert pir.name == f"{NAME} PIR 0"


async def test_update_address(hass):
    """Test update address works."""
    config_entry = await setup_axis_integration(hass)
    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]
    assert device.api.config.host == "1.2.3.4"

    with patch(
        "homeassistant.components.axis.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, respx.mock:
        mock_default_vapix_requests(respx, "2.3.4.5")
        await hass.config_entries.flow.async_init(
            AXIS_DOMAIN,
            data={
                "host": "2.3.4.5",
                "port": 80,
                "hostname": "name",
                "properties": {"macaddress": MAC},
            },
            context={"source": SOURCE_ZEROCONF},
        )
        await hass.async_block_till_done()

    assert device.api.config.host == "2.3.4.5"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_device_unavailable(hass):
    """Successful setup."""
    config_entry = await setup_axis_integration(hass)
    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]
    device.async_connection_status_callback(status=False)
    assert not device.available


async def test_device_reset(hass):
    """Successfully reset device."""
    config_entry = await setup_axis_integration(hass)
    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]
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

    await axis_device.shutdown(None)

    assert len(axis_device.api.stream.stop.mock_calls) == 1


async def test_get_device_fails(hass):
    """Device unauthorized yields authentication required error."""
    with patch(
        "axis.vapix.Vapix.request", side_effect=axislib.Unauthorized
    ), pytest.raises(axis.errors.AuthenticationRequired):
        await axis.device.get_device(hass, host="", port="", username="", password="")


async def test_get_device_device_unavailable(hass):
    """Device unavailable yields cannot connect error."""
    with patch(
        "axis.vapix.Vapix.request", side_effect=axislib.RequestError
    ), pytest.raises(axis.errors.CannotConnect):
        await axis.device.get_device(hass, host="", port="", username="", password="")


async def test_get_device_unknown_error(hass):
    """Device yield unknown error."""
    with patch(
        "axis.vapix.Vapix.request", side_effect=axislib.AxisException
    ), pytest.raises(axis.errors.AuthenticationRequired):
        await axis.device.get_device(hass, host="", port="", username="", password="")
