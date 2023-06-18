"""Test Axis device."""
from unittest import mock
from unittest.mock import Mock, patch

import axis as axislib
import pytest

from homeassistant.components import axis, zeroconf
from homeassistant.components.axis.const import DOMAIN as AXIS_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    API_DISCOVERY_BASIC_DEVICE_INFO,
    API_DISCOVERY_MQTT,
    FORMATTED_MAC,
    MAC,
    NAME,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


@pytest.fixture(name="forward_entry_setup")
def hass_mock_forward_entry_setup(hass):
    """Mock async_forward_entry_setup."""
    with patch.object(hass.config_entries, "async_forward_entry_setup") as forward_mock:
        yield forward_mock


async def test_device_setup(
    hass: HomeAssistant, forward_entry_setup, config, setup_config_entry
) -> None:
    """Successful setup."""
    device = hass.data[AXIS_DOMAIN][setup_config_entry.entry_id]

    assert device.api.vapix.firmware_version == "9.10.1"
    assert device.api.vapix.product_number == "M1065-LW"
    assert device.api.vapix.product_type == "Network Camera"
    assert device.api.vapix.serial_number == "00408C123456"

    assert len(forward_entry_setup.mock_calls) == 4
    assert forward_entry_setup.mock_calls[0][1][1] == "binary_sensor"
    assert forward_entry_setup.mock_calls[1][1][1] == "camera"
    assert forward_entry_setup.mock_calls[2][1][1] == "light"
    assert forward_entry_setup.mock_calls[3][1][1] == "switch"

    assert device.host == config[CONF_HOST]
    assert device.model == config[CONF_MODEL]
    assert device.name == config[CONF_NAME]
    assert device.unique_id == FORMATTED_MAC

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(AXIS_DOMAIN, device.unique_id)}
    )

    assert device_entry.configuration_url == device.api.config.url


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_BASIC_DEVICE_INFO])
async def test_device_info(hass: HomeAssistant, setup_config_entry) -> None:
    """Verify other path of device information works."""
    device = hass.data[AXIS_DOMAIN][setup_config_entry.entry_id]

    assert device.api.vapix.firmware_version == "9.80.1"
    assert device.api.vapix.product_number == "M1065-LW"
    assert device.api.vapix.product_type == "Network Camera"
    assert device.api.vapix.serial_number == "00408C123456"


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_MQTT])
async def test_device_support_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_config_entry
) -> None:
    """Successful setup."""
    mqtt_mock.async_subscribe.assert_called_with(f"{MAC}/#", mock.ANY, 0, "utf-8")

    topic = f"{MAC}/event/tns:onvif/Device/tns:axis/Sensor/PIR/$source/sensor/0"
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


async def test_update_address(
    hass: HomeAssistant, setup_config_entry, mock_vapix_requests
) -> None:
    """Test update address works."""
    device = hass.data[AXIS_DOMAIN][setup_config_entry.entry_id]
    assert device.api.config.host == "1.2.3.4"

    with patch(
        "homeassistant.components.axis.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        mock_vapix_requests("2.3.4.5")
        await hass.config_entries.flow.async_init(
            AXIS_DOMAIN,
            data=zeroconf.ZeroconfServiceInfo(
                host="2.3.4.5",
                addresses=["2.3.4.5"],
                hostname="mock_hostname",
                name="name",
                port=80,
                properties={"macaddress": MAC},
                type="mock_type",
            ),
            context={"source": SOURCE_ZEROCONF},
        )
        await hass.async_block_till_done()

    assert device.api.config.host == "2.3.4.5"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_device_unavailable(
    hass: HomeAssistant, setup_config_entry, mock_rtsp_event, mock_rtsp_signal_state
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


async def test_device_reset(hass: HomeAssistant, setup_config_entry) -> None:
    """Successfully reset device."""
    device = hass.data[AXIS_DOMAIN][setup_config_entry.entry_id]
    result = await device.async_reset()
    assert result is True


async def test_device_not_accessible(
    hass: HomeAssistant, config_entry, setup_default_vapix_requests
) -> None:
    """Failed setup schedules a retry of setup."""
    with patch.object(axis, "get_axis_device", side_effect=axis.errors.CannotConnect):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.data[AXIS_DOMAIN] == {}


async def test_device_trigger_reauth_flow(
    hass: HomeAssistant, config_entry, setup_default_vapix_requests
) -> None:
    """Failed authentication trigger a reauthentication flow."""
    with patch.object(
        axis, "get_axis_device", side_effect=axis.errors.AuthenticationRequired
    ), patch.object(hass.config_entries.flow, "async_init") as mock_flow_init:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        mock_flow_init.assert_called_once()
    assert hass.data[AXIS_DOMAIN] == {}


async def test_device_unknown_error(
    hass: HomeAssistant, config_entry, setup_default_vapix_requests
) -> None:
    """Unknown errors are handled."""
    with patch.object(axis, "get_axis_device", side_effect=Exception):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.data[AXIS_DOMAIN] == {}


async def test_shutdown(config) -> None:
    """Successful shutdown."""
    hass = Mock()
    entry = Mock()
    entry.data = config

    axis_device = axis.device.AxisNetworkDevice(hass, entry, Mock())

    await axis_device.shutdown(None)

    assert len(axis_device.api.stream.stop.mock_calls) == 1


async def test_get_device_fails(hass: HomeAssistant, config) -> None:
    """Device unauthorized yields authentication required error."""
    with patch(
        "axis.vapix.vapix.Vapix.request", side_effect=axislib.Unauthorized
    ), pytest.raises(axis.errors.AuthenticationRequired):
        await axis.device.get_axis_device(hass, config)


async def test_get_device_device_unavailable(hass: HomeAssistant, config) -> None:
    """Device unavailable yields cannot connect error."""
    with patch(
        "axis.vapix.vapix.Vapix.request", side_effect=axislib.RequestError
    ), pytest.raises(axis.errors.CannotConnect):
        await axis.device.get_axis_device(hass, config)


async def test_get_device_unknown_error(hass: HomeAssistant, config) -> None:
    """Device yield unknown error."""
    with patch(
        "axis.vapix.vapix.Vapix.request", side_effect=axislib.AxisException
    ), pytest.raises(axis.errors.AuthenticationRequired):
        await axis.device.get_axis_device(hass, config)
