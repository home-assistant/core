"""Test Axis device."""
from copy import deepcopy
from unittest import mock

import axis as axislib
from axis.event_stream import OPERATION_INITIALIZED
import pytest

from homeassistant import config_entries
from homeassistant.components import axis
from homeassistant.components.axis.const import (
    CONF_CAMERA,
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
from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_mock_mqtt_component,
)

MAC = "00408C12345"
MODEL = "model"
NAME = "name"

ENTRY_OPTIONS = {CONF_CAMERA: True, CONF_EVENTS: True}

ENTRY_CONFIG = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 80,
    CONF_MAC: MAC,
    CONF_MODEL: MODEL,
    CONF_NAME: NAME,
}

DEFAULT_API_DISCOVERY = {
    "method": "getApiList",
    "apiVersion": "1.0",
    "data": {
        "apiList": [
            {"id": "api-discovery", "version": "1.0", "name": "API Discovery Service"},
            {"id": "param-cgi", "version": "1.0", "name": "Legacy Parameter Handling"},
        ]
    },
}

DEFAULT_BRAND = """root.Brand.Brand=AXIS
root.Brand.ProdFullName=AXIS M1065-LW Network Camera
root.Brand.ProdNbr=M1065-LW
root.Brand.ProdShortName=AXIS M1065-LW
root.Brand.ProdType=Network Camera
root.Brand.ProdVariant=
root.Brand.WebURL=http://www.axis.com
"""

DEFAULT_PORTS = """root.Input.NbrOfInputs=1
root.IOPort.I0.Configurable=no
root.IOPort.I0.Direction=input
root.IOPort.I0.Input.Name=PIR sensor
root.IOPort.I0.Input.Trig=closed
root.Output.NbrOfOutputs=0
"""

DEFAULT_PROPERTIES = """root.Properties.API.HTTP.Version=3
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


async def setup_axis_integration(
    hass,
    config=ENTRY_CONFIG,
    options=ENTRY_OPTIONS,
    api_discovery=DEFAULT_API_DISCOVERY,
    brand=DEFAULT_BRAND,
    ports=DEFAULT_PORTS,
    properties=DEFAULT_PROPERTIES,
):
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

    def mock_update_api_discovery(self):
        self.process_raw(api_discovery)

    def mock_update_brand(self):
        self.process_raw(brand)

    def mock_update_ports(self):
        self.process_raw(ports)

    def mock_update_properties(self):
        self.process_raw(properties)

    with patch(
        "axis.api_discovery.ApiDiscovery.update", new=mock_update_api_discovery
    ), patch("axis.param_cgi.Brand.update_brand", new=mock_update_brand), patch(
        "axis.param_cgi.Ports.update_ports", new=mock_update_ports
    ), patch(
        "axis.param_cgi.Properties.update_properties", new=mock_update_properties
    ), patch(
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

        entry = device.config_entry

    assert len(forward_entry_setup.mock_calls) == 3
    assert forward_entry_setup.mock_calls[0][1] == (entry, "binary_sensor")
    assert forward_entry_setup.mock_calls[1][1] == (entry, "camera")
    assert forward_entry_setup.mock_calls[2][1] == (entry, "switch")

    assert device.host == ENTRY_CONFIG[CONF_HOST]
    assert device.model == ENTRY_CONFIG[CONF_MODEL]
    assert device.name == ENTRY_CONFIG[CONF_NAME]
    assert device.serial == ENTRY_CONFIG[CONF_MAC]


async def test_device_support_mqtt(hass):
    """Successful setup."""
    api_discovery = deepcopy(DEFAULT_API_DISCOVERY)
    api_discovery["data"]["apiList"].append(
        {"id": "mqtt-client", "version": "1.0", "name": "MQTT Client API"}
    )
    get_client_status = {"data": {"status": {"state": "active"}}}

    mock_mqtt = await async_mock_mqtt_component(hass)

    with patch(
        "axis.mqtt.MqttClient.get_client_status", return_value=get_client_status
    ):
        await setup_axis_integration(hass, api_discovery=api_discovery)

    mock_mqtt.async_subscribe.assert_called_with(f"{MAC}/#", mock.ANY, 0, "utf-8")

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
        "axis.api_discovery.ApiDiscovery.update", side_effect=axislib.Unauthorized
    ), pytest.raises(axis.errors.AuthenticationRequired):
        await axis.device.get_device(hass, host="", port="", username="", password="")


async def test_get_device_device_unavailable(hass):
    """Device unavailable yields cannot connect error."""
    with patch(
        "axis.api_discovery.ApiDiscovery.update", side_effect=axislib.RequestError
    ), pytest.raises(axis.errors.CannotConnect):
        await axis.device.get_device(hass, host="", port="", username="", password="")


async def test_get_device_unknown_error(hass):
    """Device yield unknown error."""
    with patch(
        "axis.api_discovery.ApiDiscovery.update", side_effect=axislib.AxisException
    ), pytest.raises(axis.errors.AuthenticationRequired):
        await axis.device.get_device(hass, host="", port="", username="", password="")
