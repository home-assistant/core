"""Test Axis device."""

from collections.abc import Callable
from ipaddress import ip_address
from types import MappingProxyType
from typing import Any
from unittest import mock
from unittest.mock import ANY, Mock, call, patch

import axis as axislib
import pytest

from homeassistant.components import axis, zeroconf
from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_ZEROCONF, ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import (
    API_DISCOVERY_BASIC_DEVICE_INFO,
    API_DISCOVERY_MQTT,
    FORMATTED_MAC,
    MAC,
    NAME,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


@pytest.mark.parametrize(
    ("api_discovery_items", "version"),
    [
        ({}, "9.10.1"),
        (API_DISCOVERY_BASIC_DEVICE_INFO, "9.80.1"),
    ],
)
async def test_device_registry_entry(
    config_entry_setup: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    version: str,
) -> None:
    """Successful setup."""
    device_entry = device_registry.async_get_device(
        identifiers={(AXIS_DOMAIN, config_entry_setup.unique_id)}
    )

    assert device_entry.configuration_url == "http://1.2.3.4:80"
    assert device_entry.connections == {(CONNECTION_NETWORK_MAC, FORMATTED_MAC)}
    assert device_entry.identifiers == {(AXIS_DOMAIN, FORMATTED_MAC)}
    assert device_entry.manufacturer == "Axis Communications AB"
    assert device_entry.model == "A1234 Network Camera"
    assert device_entry.name == "home"
    assert device_entry.sw_version == version


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_MQTT])
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_support_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Successful setup."""
    mqtt_call = call(f"axis/{MAC}/#", mock.ANY, 0, "utf-8", ANY)
    assert mqtt_call in mqtt_mock.async_subscribe.call_args_list

    topic = f"axis/{MAC}/event/tns:onvif/Device/tns:axis/Sensor/PIR/$source/sensor/0"
    message = (
        b'{"timestamp": 1590258472044, "topic": "onvif:Device/axis:Sensor/PIR",'
        b' "message": {"source": {"sensor": "0"}, "key": {}, "data": {"state": "1"}}}'
    )

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 0
    async_fire_mqtt_message(hass, topic, message)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1

    pir = hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_pir_0")
    assert pir.state == STATE_ON
    assert pir.name == f"{NAME} PIR 0"


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_MQTT])
@pytest.mark.parametrize("mqtt_status_code", [401])
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_support_mqtt_low_privilege(mqtt_mock: MqttMockHAClient) -> None:
    """Successful setup."""
    mqtt_call = call(f"{MAC}/#", mock.ANY, 0, "utf-8")
    assert mqtt_call not in mqtt_mock.async_subscribe.call_args_list


async def test_update_address(
    hass: HomeAssistant,
    config_entry_setup: ConfigEntry,
    mock_requests: Callable[[str], None],
) -> None:
    """Test update address works."""
    hub = config_entry_setup.runtime_data
    assert hub.api.config.host == "1.2.3.4"

    mock_requests("2.3.4.5")
    await hass.config_entries.flow.async_init(
        AXIS_DOMAIN,
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("2.3.4.5"),
            ip_addresses=[ip_address("2.3.4.5")],
            hostname="mock_hostname",
            name="name",
            port=80,
            properties={"macaddress": MAC},
            type="mock_type",
        ),
        context={"source": SOURCE_ZEROCONF},
    )
    await hass.async_block_till_done()

    assert hub.api.config.host == "2.3.4.5"


@pytest.mark.usefixtures("config_entry_setup")
async def test_device_unavailable(
    hass: HomeAssistant,
    mock_rtsp_event: Callable[[str, str, str, str, str, str], None],
    mock_rtsp_signal_state: Callable[[bool], None],
) -> None:
    """Successful setup."""
    # Provide an entity that can be used to verify connection state on
    mock_rtsp_event(
        topic="tns1:AudioSource/tnsaxis:TriggerLevel",
        data_type="triggered",
        data_value="10",
        source_name="channel",
        source_idx="1",
    )
    await hass.async_block_till_done()

    assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_sound_1").state == STATE_OFF

    # Connection to device has failed

    mock_rtsp_signal_state(connected=False)
    await hass.async_block_till_done()

    assert (
        hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_sound_1").state
        == STATE_UNAVAILABLE
    )

    # Connection to device has been restored

    mock_rtsp_signal_state(connected=True)
    await hass.async_block_till_done()

    assert hass.states.get(f"{BINARY_SENSOR_DOMAIN}.{NAME}_sound_1").state == STATE_OFF


@pytest.mark.usefixtures("mock_default_requests")
async def test_device_not_accessible(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Failed setup schedules a retry of setup."""
    with patch.object(axis, "get_axis_api", side_effect=axis.errors.CannotConnect):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.data[AXIS_DOMAIN] == {}


@pytest.mark.usefixtures("mock_default_requests")
async def test_device_trigger_reauth_flow(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Failed authentication trigger a reauthentication flow."""
    with (
        patch.object(
            axis, "get_axis_api", side_effect=axis.errors.AuthenticationRequired
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_flow_init,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        mock_flow_init.assert_called_once()
    assert hass.data[AXIS_DOMAIN] == {}


@pytest.mark.usefixtures("mock_default_requests")
async def test_device_unknown_error(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Unknown errors are handled."""
    with patch.object(axis, "get_axis_api", side_effect=Exception):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.data[AXIS_DOMAIN] == {}


async def test_shutdown(config_entry_data: MappingProxyType[str, Any]) -> None:
    """Successful shutdown."""
    hass = Mock()
    entry = Mock()
    entry.data = config_entry_data

    mock_api = Mock()
    mock_api.vapix.serial_number = FORMATTED_MAC
    axis_device = axis.hub.AxisHub(hass, entry, mock_api)

    await axis_device.shutdown(None)

    assert len(axis_device.api.stream.stop.mock_calls) == 1


async def test_get_device_fails(
    hass: HomeAssistant, config_entry_data: MappingProxyType[str, Any]
) -> None:
    """Device unauthorized yields authentication required error."""
    with (
        patch(
            "axis.interfaces.vapix.Vapix.initialize", side_effect=axislib.Unauthorized
        ),
        pytest.raises(axis.errors.AuthenticationRequired),
    ):
        await axis.hub.get_axis_api(hass, config_entry_data)


async def test_get_device_device_unavailable(
    hass: HomeAssistant, config_entry_data: MappingProxyType[str, Any]
) -> None:
    """Device unavailable yields cannot connect error."""
    with (
        patch("axis.interfaces.vapix.Vapix.request", side_effect=axislib.RequestError),
        pytest.raises(axis.errors.CannotConnect),
    ):
        await axis.hub.get_axis_api(hass, config_entry_data)


async def test_get_device_unknown_error(
    hass: HomeAssistant, config_entry_data: MappingProxyType[str, Any]
) -> None:
    """Device yield unknown error."""
    with (
        patch("axis.interfaces.vapix.Vapix.request", side_effect=axislib.AxisException),
        pytest.raises(axis.errors.AuthenticationRequired),
    ):
        await axis.hub.get_axis_api(hass, config_entry_data)
